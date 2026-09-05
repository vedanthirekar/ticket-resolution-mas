from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.agents.contracts import AdjustMembershipCreditAction, RefundPaymentAction
from luma.db.models.billing import Payment, PaymentEvent, Refund
from luma.db.models.case_management import (
    ActionIntent,
    Approval,
    ExecutionAttempt,
    OperationsAccount,
    SupportCase,
)
from luma.db.models.membership import Membership, MembershipLedgerEntry
from luma.domain.cases import CaseStatus
from luma.services.cases import transition_case
from luma.services.jobs import enqueue_approval_resume
from luma.services.refunds import create_pending_refund


class ActionValidationError(ValueError):
    """An action is malformed, unauthorized, or stale."""


@dataclass(frozen=True, slots=True)
class ActionExecutionResult:
    status: str
    receipt: dict[str, Any]
    error_code: str | None = None


def _stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _parse_command(payload: dict[str, Any]) -> RefundPaymentAction | AdjustMembershipCreditAction:
    try:
        if payload.get("action_type") == "refund_payment":
            return RefundPaymentAction.model_validate(payload)
        if payload.get("action_type") == "adjust_membership_credit":
            return AdjustMembershipCreditAction.model_validate(payload)
    except ValidationError as exc:
        raise ActionValidationError(f"invalid action payload: {exc}") from exc
    raise ActionValidationError("unsupported action type")


async def _refund_snapshot(
    session: AsyncSession, *, case: SupportCase, command: RefundPaymentAction
) -> tuple[Payment, dict[str, Any]]:
    payment = await session.scalar(
        select(Payment)
        .where(Payment.public_reference == command.payment_reference)
        .with_for_update()
    )
    if payment is None or case.customer_id is None or payment.customer_id != case.customer_id:
        raise ActionValidationError("refund target is not owned by the case customer")
    reserved = int(
        await session.scalar(
            select(func.coalesce(func.sum(Refund.amount_cents), 0)).where(
                Refund.payment_id == payment.id,
                Refund.status.in_(("pending", "succeeded")),
            )
        )
        or 0
    )
    refundable = payment.captured_amount_cents - reserved
    if command.amount_cents > refundable:
        raise ActionValidationError("refund exceeds the currently refundable amount")
    return payment, {
        "payment_reference": payment.public_reference,
        "status": payment.status,
        "captured_amount_cents": payment.captured_amount_cents,
        "refunded_amount_cents": payment.refunded_amount_cents,
        "reserved_refund_amount_cents": reserved,
        "refundable_amount_cents": refundable,
    }


async def _membership_snapshot(
    session: AsyncSession, *, case: SupportCase, command: AdjustMembershipCreditAction
) -> tuple[Membership, dict[str, Any]]:
    membership = await session.scalar(
        select(Membership)
        .where(Membership.public_reference == command.membership_reference)
        .with_for_update()
    )
    if membership is None or case.customer_id is None or membership.customer_id != case.customer_id:
        raise ActionValidationError("membership target is not owned by the case customer")
    balance = int(
        await session.scalar(
            select(func.coalesce(func.sum(MembershipLedgerEntry.credit_delta), 0)).where(
                MembershipLedgerEntry.membership_id == membership.id
            )
        )
        or 0
    )
    return membership, {
        "membership_reference": membership.public_reference,
        "status": membership.status,
        "derived_balance": balance,
    }


async def create_action_intent(
    session: AsyncSession,
    *,
    case_id: UUID,
    case_run_id: UUID,
    action_payload: dict[str, Any],
) -> ActionIntent:
    """Freeze an exact command and its authoritative before-state for approval."""
    idempotency_key = f"case-run:{case_run_id}:action:1"
    existing = await session.scalar(
        select(ActionIntent)
        .where(ActionIntent.idempotency_key == idempotency_key)
        .with_for_update()
    )
    if existing is not None:
        if existing.action_payload.get("command") != action_payload:
            raise ActionValidationError("case run attempted to replace its immutable action")
        return existing

    support_case = await session.scalar(
        select(SupportCase).where(SupportCase.id == case_id).with_for_update()
    )
    if support_case is None:
        raise ActionValidationError("case does not exist")
    command = _parse_command(action_payload)
    if isinstance(command, RefundPaymentAction):
        _, snapshot = await _refund_snapshot(session, case=support_case, command=command)
        target_type, target_reference = "payment", command.payment_reference
    else:
        _, snapshot = await _membership_snapshot(session, case=support_case, command=command)
        target_type, target_reference = "membership", command.membership_reference

    intent_id = uuid4()
    frozen_payload = {
        "command": command.model_dump(mode="json"),
        "before_state": snapshot,
        "command_hash": _stable_hash(command.model_dump(mode="json")),
    }
    intent = ActionIntent(
        id=intent_id,
        public_reference=f"ACT-{intent_id.hex[:12].upper()}",
        case_id=case_id,
        case_run_id=case_run_id,
        action_type=command.action_type,
        target_type=target_type,
        target_reference=target_reference,
        action_payload=frozen_payload,
        status="pending_approval",
        idempotency_key=idempotency_key,
    )
    session.add(intent)
    if support_case.status == CaseStatus.PROCESSING.value:
        await transition_case(
            session,
            case_id=case_id,
            to_status=CaseStatus.PENDING_APPROVAL,
            event_type="action_approval_requested",
            actor_type="system",
            actor_reference="resolution_engine",
            payload={"action_intent_reference": intent.public_reference},
        )
    await session.flush()
    return intent


async def decide_action(
    session: AsyncSession,
    *,
    action_reference: str,
    account: OperationsAccount,
    decision: str,
    rationale: str,
) -> Approval:
    if decision not in {"approved", "rejected"}:
        raise ActionValidationError("decision must be approved or rejected")
    if not account.active:
        raise ActionValidationError("operations account is inactive")
    if not rationale.strip():
        raise ActionValidationError("approval rationale must not be blank")
    intent = await session.scalar(
        select(ActionIntent)
        .where(ActionIntent.public_reference == action_reference)
        .with_for_update()
    )
    if intent is None:
        raise ActionValidationError("action intent does not exist")
    existing = await session.scalar(select(Approval).where(Approval.action_intent_id == intent.id))
    if existing is not None:
        if existing.decision != decision:
            raise ActionValidationError("action already has a different approval decision")
        await enqueue_approval_resume(
            session,
            case_id=intent.case_id,
            action_reference=intent.public_reference,
        )
        return existing
    if intent.status != "pending_approval":
        raise ActionValidationError("action is not pending approval")
    approval = Approval(
        action_intent_id=intent.id,
        decided_by_account_id=account.id,
        decision=decision,
        rationale=rationale.strip(),
        decided_at=datetime.now(UTC),
    )
    session.add(approval)
    intent.status = decision
    await enqueue_approval_resume(
        session,
        case_id=intent.case_id,
        action_reference=intent.public_reference,
    )
    await session.flush()
    return approval


async def execute_approved_action(
    session: AsyncSession, *, action_reference: str
) -> ActionExecutionResult:
    """Revalidate and execute once. The caller commits the entire transaction."""
    intent = await session.scalar(
        select(ActionIntent)
        .where(ActionIntent.public_reference == action_reference)
        .with_for_update()
    )
    if intent is None:
        raise ActionValidationError("action intent does not exist")
    prior = await session.scalar(
        select(ExecutionAttempt)
        .where(
            ExecutionAttempt.action_intent_id == intent.id,
            ExecutionAttempt.status == "succeeded",
        )
        .order_by(ExecutionAttempt.attempt_number.desc())
        .limit(1)
    )
    if prior is not None:
        return ActionExecutionResult(status="succeeded", receipt=prior.response_payload)
    approval = await session.scalar(select(Approval).where(Approval.action_intent_id == intent.id))
    if approval is None or approval.decision != "approved" or intent.status != "approved":
        raise ActionValidationError("action lacks a valid approval")

    attempt_count = int(
        await session.scalar(
            select(func.count(ExecutionAttempt.id)).where(
                ExecutionAttempt.action_intent_id == intent.id
            )
        )
        or 0
    )
    attempt = ExecutionAttempt(
        action_intent_id=intent.id,
        attempt_number=attempt_count + 1,
        executor="luma_mock_action_executor_v1",
        status="started",
        response_payload={},
        started_at=datetime.now(UTC),
    )
    session.add(attempt)
    intent.status = "executing"
    case = await session.scalar(
        select(SupportCase).where(SupportCase.id == intent.case_id).with_for_update()
    )
    assert case is not None
    command = _parse_command(intent.action_payload["command"])
    expected = intent.action_payload["before_state"]
    try:
        if isinstance(command, RefundPaymentAction):
            payment, current = await _refund_snapshot(session, case=case, command=command)
            if current != expected:
                raise ActionValidationError("payment state changed after approval request")
            refund = await create_pending_refund(
                session,
                payment_id=payment.id,
                public_reference=f"REF-{intent.id.hex[:12].upper()}",
                amount_cents=command.amount_cents,
                reason_code=command.reason_code,
                idempotency_key=intent.idempotency_key,
            )
            refund.status = "succeeded"
            refund.completed_at = datetime.now(UTC)
            refund.processor_reference = f"MOCK-{intent.id.hex.upper()}"
            payment.refunded_amount_cents += command.amount_cents
            payment.status = (
                "refunded"
                if payment.refunded_amount_cents == payment.captured_amount_cents
                else "partially_refunded"
            )
            session.add(
                PaymentEvent(
                    public_reference=f"PEVT-{intent.id.hex[:12].upper()}",
                    payment_id=payment.id,
                    event_type="refund_succeeded",
                    amount_cents=command.amount_cents,
                    actor_type="system",
                    actor_reference="luma_resolution_engine",
                    occurred_at=datetime.now(UTC),
                    processor_event_reference=refund.processor_reference,
                    correlation_reference=intent.public_reference,
                    event_metadata={"approval_reference": str(approval.id)},
                )
            )
            receipt = {
                "action_type": command.action_type,
                "action_intent_reference": intent.public_reference,
                "target_reference": payment.public_reference,
                "refund_reference": refund.public_reference,
                "amount_cents": command.amount_cents,
                "status": "succeeded",
            }
        else:
            membership, current = await _membership_snapshot(session, case=case, command=command)
            if current != expected:
                raise ActionValidationError("membership state changed after approval request")
            entry = MembershipLedgerEntry(
                public_reference=f"LED-{intent.id.hex[:12].upper()}",
                membership_id=membership.id,
                entry_type="correction",
                credit_delta=command.credit_delta,
                effective_at=datetime.now(UTC),
                actor_type="system",
                actor_reference="luma_resolution_engine",
                reason_code=command.reason_code,
                approval_reference=str(approval.id),
                idempotency_key=intent.idempotency_key,
            )
            session.add(entry)
            receipt = {
                "action_type": command.action_type,
                "action_intent_reference": intent.public_reference,
                "target_reference": membership.public_reference,
                "ledger_reference": entry.public_reference,
                "credit_delta": command.credit_delta,
                "status": "succeeded",
            }
    except ActionValidationError as exc:
        intent.status = "failed"
        attempt.status = "failed"
        attempt.error_code = "stale_or_invalid_action"
        attempt.error_detail = str(exc)
        attempt.completed_at = datetime.now(UTC)
        return ActionExecutionResult(
            status="failed", receipt={}, error_code="stale_or_invalid_action"
        )

    intent.status = "succeeded"
    attempt.status = "succeeded"
    external_reference = receipt.get("refund_reference") or receipt.get("ledger_reference")
    attempt.external_reference = external_reference if isinstance(external_reference, str) else None
    attempt.response_payload = receipt
    attempt.completed_at = datetime.now(UTC)
    await session.flush()
    return ActionExecutionResult(status="succeeded", receipt=receipt)
