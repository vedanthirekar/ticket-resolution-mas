from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.case_management import (
    CaseEvent,
    CustomerCommunication,
    OperationsAccount,
    SupportCase,
)
from luma.domain.cases import CaseStatus


class CommunicationWorkflowError(ValueError):
    """The requested customer communication operation is unsafe or invalid."""


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_contact_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if len(normalized) > 320 or _EMAIL_PATTERN.fullmatch(normalized) is None:
        raise CommunicationWorkflowError("contact_email must be a valid email address")
    return normalized


async def _append_event(
    session: AsyncSession,
    *,
    support_case: SupportCase,
    event_type: str,
    actor_type: str,
    actor_reference: str,
    payload: dict[str, object],
    occurred_at: datetime,
) -> None:
    sequence = await session.scalar(
        select(func.coalesce(func.max(CaseEvent.sequence), 0) + 1).where(
            CaseEvent.case_id == support_case.id
        )
    )
    support_case.version += 1
    session.add(
        CaseEvent(
            case_id=support_case.id,
            sequence=sequence,
            event_type=event_type,
            actor_type=actor_type,
            actor_reference=actor_reference,
            occurred_at=occurred_at,
            payload=payload,
        )
    )


def _action_confirmation(receipt: dict[str, Any] | None) -> list[str]:
    if not receipt:
        return []
    if receipt.get("action_type") == "refund_payment" and isinstance(
        receipt.get("amount_cents"), int
    ):
        detail = f"Refund completed: ${receipt['amount_cents'] / 100:,.2f}"
    elif receipt.get("action_type") == "adjust_membership_credit" and isinstance(
        receipt.get("credit_delta"), int
    ):
        delta = receipt["credit_delta"]
        detail = f"Membership credit adjustment completed: {delta:+d} credit(s)"
    else:
        detail = "The approved account action was completed."
    reference = (
        receipt.get("refund_reference")
        or receipt.get("ledger_reference")
        or receipt.get("action_intent_reference")
    )
    lines = ["", "Action confirmation", detail]
    if isinstance(reference, str):
        lines.append(f"Confirmation reference: {reference}")
    return lines


def build_final_email(
    *,
    case_reference: str,
    customer_response: str,
    execution_receipt: dict[str, Any] | None = None,
) -> tuple[str, str]:
    cleaned_response = customer_response.strip()
    if not cleaned_response:
        raise CommunicationWorkflowError("customer response must not be blank")
    subject = f"Resolution for your Luma Wellness case {case_reference}"
    lines = ["Hello,", "", cleaned_response]
    lines.extend(_action_confirmation(execution_receipt))
    lines.extend(["", f"Case reference: {case_reference}", "", "Luma Wellness Support"])
    return subject, "\n".join(lines)


async def prepare_final_email(
    session: AsyncSession,
    *,
    support_case: SupportCase,
    customer_response: str,
    execution_receipt: dict[str, Any] | None = None,
) -> CustomerCommunication | None:
    """Prepare one final email after resolution; cases without an address are skipped."""
    if support_case.status != CaseStatus.RESOLVED.value:
        raise CommunicationWorkflowError("a final email can only be prepared after resolution")
    recipient = normalize_contact_email(support_case.contact_email)
    if recipient is None:
        return None
    existing = await session.scalar(
        select(CustomerCommunication)
        .where(
            CustomerCommunication.case_id == support_case.id,
            CustomerCommunication.communication_type == "final_resolution",
        )
        .with_for_update()
    )
    if existing is not None:
        return existing

    subject, body = build_final_email(
        case_reference=support_case.public_reference,
        customer_response=customer_response,
        execution_receipt=execution_receipt,
    )
    communication = CustomerCommunication(
        case_id=support_case.id,
        communication_type="final_resolution",
        channel="email",
        recipient_email=recipient,
        subject=subject,
        body=body,
        status="prepared",
    )
    session.add(communication)
    now = datetime.now(UTC)
    await _append_event(
        session,
        support_case=support_case,
        event_type="customer_email_draft_prepared",
        actor_type="system",
        actor_reference="communication_service",
        payload={"channel": "email"},
        occurred_at=now,
    )
    await session.flush()
    return communication


async def _locked_case_and_communication(
    session: AsyncSession, case_reference: str
) -> tuple[SupportCase, CustomerCommunication]:
    support_case = await session.scalar(
        select(SupportCase)
        .where(
            SupportCase.public_reference == case_reference,
            ~SupportCase.external_request_key.startswith("eval:"),
        )
        .with_for_update()
    )
    if support_case is None:
        raise CommunicationWorkflowError("case does not exist")
    if support_case.status != CaseStatus.RESOLVED.value:
        raise CommunicationWorkflowError("case must be resolved before customer notification")
    communication = await session.scalar(
        select(CustomerCommunication)
        .where(
            CustomerCommunication.case_id == support_case.id,
            CustomerCommunication.communication_type == "final_resolution",
        )
        .with_for_update()
    )
    if communication is None:
        raise CommunicationWorkflowError("case has no prepared final email")
    return support_case, communication


def _clean_draft(subject: str, body: str) -> tuple[str, str]:
    cleaned_subject = subject.strip()
    cleaned_body = body.strip()
    if not cleaned_subject or len(cleaned_subject) > 240:
        raise CommunicationWorkflowError("email subject must contain 1 to 240 characters")
    if not cleaned_body or len(cleaned_body) > 10_000:
        raise CommunicationWorkflowError("email body must contain 1 to 10000 characters")
    return cleaned_subject, cleaned_body


async def update_final_email_draft(
    session: AsyncSession,
    *,
    case_reference: str,
    account: OperationsAccount,
    subject: str,
    body: str,
) -> CustomerCommunication:
    support_case, communication = await _locked_case_and_communication(session, case_reference)
    if communication.status != "prepared":
        raise CommunicationWorkflowError("a sent email cannot be edited")
    cleaned_subject, cleaned_body = _clean_draft(subject, body)
    communication.subject = cleaned_subject
    communication.body = cleaned_body
    now = datetime.now(UTC)
    await _append_event(
        session,
        support_case=support_case,
        event_type="customer_email_draft_updated",
        actor_type="employee",
        actor_reference=account.username,
        payload={"channel": "email"},
        occurred_at=now,
    )
    await session.flush()
    return communication


async def mock_send_final_email(
    session: AsyncSession,
    *,
    case_reference: str,
    account: OperationsAccount,
    subject: str,
    body: str,
) -> CustomerCommunication:
    support_case, communication = await _locked_case_and_communication(session, case_reference)
    cleaned_subject, cleaned_body = _clean_draft(subject, body)
    if communication.status == "sent":
        if communication.subject != cleaned_subject or communication.body != cleaned_body:
            raise CommunicationWorkflowError("the sent email cannot be changed")
        return communication

    communication.subject = cleaned_subject
    communication.body = cleaned_body
    communication.status = "sent"
    communication.sent_at = datetime.now(UTC)
    communication.sent_by_account_id = account.id
    communication.delivery_reference = f"MOCK-EMAIL-{communication.id.hex[:12].upper()}"
    await _append_event(
        session,
        support_case=support_case,
        event_type="customer_email_mock_sent",
        actor_type="employee",
        actor_reference=account.username,
        payload={
            "channel": "email",
            "delivery_reference": communication.delivery_reference,
        },
        occurred_at=communication.sent_at,
    )
    await session.flush()
    return communication
