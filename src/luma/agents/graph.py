from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from typing import Any, Literal, cast
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from luma.agents.artifacts import (
    complete_run,
    complete_stage,
    completed_stage_output,
    persist_evidence,
    persist_plan,
    persist_policy_retrieval,
    persist_proposal,
    persist_verification,
)
from luma.agents.contracts import (
    CATEGORY_REQUIRED_EVIDENCE,
    AdjustMembershipCreditAction,
    CaseCategory,
    CaseResolutionState,
    EvidenceGateOutput,
    EvidenceRecord,
    InvestigationDecisionOutput,
    InvestigationPlanOutput,
    OperationalCall,
    PolicyAssessmentOutput,
    RefundPaymentAction,
    ResolutionProposalOutput,
    VerificationOutput,
)
from luma.agents.models import StructuredModel
from luma.agents.prompts import (
    CASE_MANAGER_PLAN_PROMPT,
    CASE_MANAGER_PROPOSAL_PROMPT,
    INVESTIGATION_AGENT_PROMPT,
    POLICY_AGENT_PROMPT,
    VERIFIER_PROMPT,
)
from luma.agents.tool_executor import TOOL_REGISTRY, execute_operational_call
from luma.config import Settings
from luma.db.models.case_management import ActionIntent, Approval, Escalation, SupportCase
from luma.db.session import Database
from luma.domain.cases import CaseStatus
from luma.retrieval.embeddings import EmbeddingProvider
from luma.retrieval.policy import fetch_policy_section, search_policy
from luma.services.actions import (
    ActionValidationError,
    create_action_intent,
    execute_approved_action,
)
from luma.services.cases import transition_case
from luma.services.communications import prepare_final_email
from luma.tools.contracts import PolicySearchInput, PolicySectionFetchInput

CATEGORY_POLICY_AREA: dict[CaseCategory, str | None] = {
    CaseCategory.DUPLICATE_PAYMENT: "payments",
    CaseCategory.CANCELLATION_FEE_DISPUTE: "cancellation",
    CaseCategory.MISSING_APPOINTMENT: "booking",
    CaseCategory.MEMBERSHIP_CREDITS: "membership",
    CaseCategory.ONLINE_BOOKING_UNAVAILABLE: "booking",
    CaseCategory.UNKNOWN: None,
}


def _uuid(value: str) -> UUID:
    return UUID(value)


def _evidence_gate(
    plan: InvestigationPlanOutput, evidence: list[EvidenceRecord]
) -> EvidenceGateOutput:
    if plan.category is CaseCategory.UNKNOWN:
        return EvidenceGateOutput(sufficient=False, reason_code="unsupported_case_category")

    # Evidence requirements are a product safety contract, not an LLM decision. The
    # model may explain investigation objectives, but it cannot add irrelevant mandatory
    # evidence that makes a supported case impossible to resolve.
    requirements = set(CATEGORY_REQUIRED_EVIDENCE[plan.category])
    known_types = {record.evidence_type for record in evidence if record.condition == "present"}
    contradictory = sorted(
        {record.evidence_type for record in evidence if record.condition == "contradictory"}
    )
    missing = sorted(requirements - known_types)
    if contradictory:
        return EvidenceGateOutput(
            sufficient=False,
            missing_evidence=missing,
            contradictions=contradictory,
            reason_code="conflicting_operational_evidence",
        )
    if missing:
        return EvidenceGateOutput(
            sufficient=False,
            missing_evidence=missing,
            reason_code="required_operational_evidence_missing",
        )
    return EvidenceGateOutput(sufficient=True)


def _material_event_date(plan: InvestigationPlanOutput, evidence: list[dict[str, Any]]) -> date:
    """Use authoritative operational time for policy versioning, not an LLM guess."""
    for key in ("scheduled_start", "requested_start", "effective_at", "occurred_at", "created_at"):
        value = _find_first(evidence, key)
        if value is None:
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            continue
    return plan.material_event_date


def _find_first(value: Any, key: str) -> str | None:
    if isinstance(value, dict):
        found = value.get(key)
        if isinstance(found, str):
            return found
        for child in value.values():
            nested = _find_first(child, key)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _find_first(child, key)
            if nested is not None:
                return nested
    return None


def _contains_value(value: Any, expected: object) -> bool:
    if value == expected:
        return True
    if isinstance(value, dict):
        return any(_contains_value(child, expected) for child in value.values())
    if isinstance(value, list):
        return any(_contains_value(child, expected) for child in value)
    return False


_DISCOVERED_REFERENCE_ARGUMENTS = frozenset(
    {"appointment_reference", "booking_attempt_reference", "membership_reference"}
)


def _call_uses_only_discovered_references(
    call: OperationalCall,
    *,
    complaint: str,
    evidence: list[EvidenceRecord],
) -> bool:
    """Reject placeholders and invented identifiers at the tool boundary."""
    discovered = {reference for record in evidence for reference in record.source_references}
    for argument_name in _DISCOVERED_REFERENCE_ARGUMENTS:
        value = call.arguments.get(argument_name)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            return False
        normalized = value.strip()
        if "<" in normalized or ">" in normalized:
            return False
        if normalized not in complaint and normalized not in discovered:
            return False
    return True


def _preverify(state: CaseResolutionState) -> dict[str, Any]:
    """Fail closed on structural safety rules before spending a verifier call."""
    proposal = ResolutionProposalOutput.model_validate(state["proposal"])
    evidence = state.get("evidence", [])
    assessment = PolicyAssessmentOutput.model_validate(state["policy_assessment"])
    failures: list[str] = []
    if not proposal.evidence_references:
        failures.append("proposal_has_no_evidence_citations")
    if not proposal.policy_references:
        failures.append("proposal_has_no_policy_citations")
    if not assessment.applicable:
        failures.append("policy_not_applicable")
    if proposal.action_payload is not None:
        try:
            if isinstance(proposal.action_payload, RefundPaymentAction):
                target = proposal.action_payload.payment_reference
                exact_value = proposal.action_payload.amount_cents
            elif isinstance(proposal.action_payload, AdjustMembershipCreditAction):
                target = proposal.action_payload.membership_reference
                exact_value = proposal.action_payload.credit_delta
            else:
                raise ValueError("unsupported action type")
            if not _contains_value(evidence, target):
                failures.append("action_target_not_in_evidence")
            if not _contains_value(evidence, exact_value):
                failures.append("action_value_not_in_evidence")
        except (ValidationError, ValueError):
            failures.append("invalid_action_contract")
    return {"passed": not failures, "failure_reasons": failures}


class CaseResolutionWorkflow:
    """Fixed, bounded manager -> investigator -> policy -> proposal workflow."""

    def __init__(
        self,
        *,
        database: Database,
        model: StructuredModel,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
        unavailable_tools: frozenset[str] = frozenset(),
    ) -> None:
        self.database = database
        self.model = model
        self.embedding_provider = embedding_provider
        self.settings = settings
        self.unavailable_tools = unavailable_tools

    async def _execute_call(
        self, session: Any, call: OperationalCall, *, customer_reference: str | None
    ) -> EvidenceRecord:
        """Execute normally, or fail closed when an eval harness injects an outage."""
        if call.tool_name in self.unavailable_tools:
            return EvidenceRecord(
                evidence_type=TOOL_REGISTRY[call.tool_name][2],
                condition="unavailable",
                tool_name=call.tool_name,
                error="evaluation fault injection: authoritative source unavailable",
            )
        return await execute_operational_call(
            session, call, expected_customer_reference=customer_reference
        )

    async def _model_call[OutputT: BaseModel](
        self,
        *,
        stage: str,
        schema: type[OutputT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> Any:
        try:
            # The provider timeout applies to each HTTP attempt. Give the whole
            # structured-output stage a separate budget so provider retries and
            # format-correction attempts are not cancelled at the first request's
            # deadline.
            async with asyncio.timeout(self.settings.model_stage_timeout_seconds):
                return await self.model.generate(
                    stage=stage,
                    schema=schema,
                    system_prompt=system_prompt,
                    payload=payload,
                )
        except TimeoutError as exc:
            raise RuntimeError(
                f"{stage} exceeded the {self.settings.model_stage_timeout_seconds:g}s "
                "model-stage timeout"
            ) from exc
        except ValidationError as exc:
            raise RuntimeError(f"{stage} model output failed validation") from exc

    async def plan_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        async with self.database.session() as session:
            cached = await completed_stage_output(session, run_id, "case_manager_plan")
        if cached is not None:
            return cached

        if not state.get("customer_reference"):
            output: dict[str, Any] = {"escalation_reason": "customer_identity_not_established"}
        else:
            invocation = await self._model_call(
                stage="case_manager_plan",
                schema=InvestigationPlanOutput,
                system_prompt=CASE_MANAGER_PLAN_PROMPT,
                payload={
                    "case_reference": state["case_reference"],
                    "case_received_at": state.get("case_received_at"),
                    "complaint": state["complaint_text"],
                    "customer_reference": state["customer_reference"],
                    "claimed_category": state.get("claimed_category"),
                    "available_evidence_types": sorted(
                        {evidence_type for _, _, evidence_type in TOOL_REGISTRY.values()}
                    ),
                },
            )
            plan = cast(InvestigationPlanOutput, invocation.value)
            plan = plan.model_copy(
                update={
                    "required_evidence_types": sorted(CATEGORY_REQUIRED_EVIDENCE[plan.category])
                }
            )
            usage = {
                "input_tokens": state.get("input_tokens", 0) + invocation.input_tokens,
                "output_tokens": state.get("output_tokens", 0) + invocation.output_tokens,
            }
            if plan.category is CaseCategory.UNKNOWN:
                output = {
                    "plan": plan.model_dump(mode="json"),
                    "escalation_reason": "unsupported_case_category",
                    **usage,
                }
            else:
                output = {
                    "plan": plan.model_dump(mode="json"),
                    "supplemental_count": 0,
                    **usage,
                }

        async with self.database.transaction() as session:
            if "plan" in output:
                await persist_plan(session, case_run_id=run_id, plan=output["plan"])
            return await complete_stage(
                session,
                case_run_id=run_id,
                stage_name="case_manager_plan",
                output=output,
            )

    async def investigation_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        async with self.database.session() as session:
            cached = await completed_stage_output(session, run_id, "investigation")
        if cached is not None:
            return cached

        plan = InvestigationPlanOutput.model_validate(state["plan"])
        records: list[EvidenceRecord] = []
        calls: list[dict[str, Any]] = []
        call_signatures: set[str] = set()
        input_tokens = state.get("input_tokens", 0)
        output_tokens = state.get("output_tokens", 0)
        escalation_reason: str | None = None

        for iteration in range(1, self.settings.agent_max_tool_calls + 1):
            invocation = await self._model_call(
                stage="investigation_decision",
                schema=InvestigationDecisionOutput,
                system_prompt=INVESTIGATION_AGENT_PROMPT,
                payload={
                    "case_reference": state["case_reference"],
                    "case_received_at": state.get("case_received_at"),
                    "complaint": state["complaint_text"],
                    "customer_reference": state["customer_reference"],
                    "claimed_category": state.get("claimed_category"),
                    "plan": plan.model_dump(mode="json"),
                    "evidence": [record.model_dump(mode="json") for record in records],
                    "available_tools": {
                        name: request_type.model_json_schema()
                        for name, (request_type, _, _) in TOOL_REGISTRY.items()
                    },
                    "remaining_tool_calls": self.settings.agent_max_tool_calls - len(records),
                },
            )
            decision = cast(InvestigationDecisionOutput, invocation.value)
            input_tokens += invocation.input_tokens
            output_tokens += invocation.output_tokens
            if decision.complete:
                break

            call = decision.next_call
            assert call is not None
            signature = json.dumps(
                {"tool_name": call.tool_name, "arguments": call.arguments}, sort_keys=True
            )
            if signature in call_signatures:
                escalation_reason = "repeated_investigation_call"
                break
            if not _call_uses_only_discovered_references(
                call,
                complaint=state["complaint_text"],
                evidence=records,
            ):
                escalation_reason = "ungrounded_investigation_reference"
                break
            call_signatures.add(signature)
            async with self.database.session() as session:
                record = await self._execute_call(
                    session, call, customer_reference=state.get("customer_reference")
                )
            records.append(record)
            calls.append(
                {
                    "iteration": iteration,
                    "call": call.model_dump(mode="json"),
                    "result_condition": record.condition,
                    "source_references": record.source_references,
                }
            )
            # The model chooses how to gather facts; deterministic code decides when the
            # declared evidence contract has been fulfilled. Do not spend more calls or
            # allow a weak model to loop after all required evidence is already present.
            if _evidence_gate(plan, records).sufficient:
                break

        output = {
            "evidence": [record.model_dump(mode="json") for record in records],
            "investigation_calls": calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        if escalation_reason is not None:
            output["escalation_reason"] = escalation_reason
        async with self.database.transaction() as session:
            await persist_evidence(session, case_run_id=run_id, records=records)
            return await complete_stage(
                session, case_run_id=run_id, stage_name="investigation", output=output
            )

    async def evidence_gate_node(self, state: CaseResolutionState) -> dict[str, Any]:
        plan = InvestigationPlanOutput.model_validate(state["plan"])
        evidence = [EvidenceRecord.model_validate(item) for item in state.get("evidence", [])]
        gate = _evidence_gate(plan, evidence)
        output: dict[str, Any] = {"evidence_gate": gate.model_dump(mode="json")}
        if not gate.sufficient:
            output["escalation_reason"] = gate.reason_code
        return output

    async def policy_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        async with self.database.session() as session:
            cached = await completed_stage_output(session, run_id, "policy")
        if cached is not None:
            return cached

        plan = InvestigationPlanOutput.model_validate(state["plan"])
        effective_on = _material_event_date(plan, state.get("evidence", []))
        location_reference = _find_first(state.get("evidence", []), "location_reference")
        service_reference = _find_first(state.get("evidence", []), "service_reference")
        request = PolicySearchInput(
            query=plan.policy_query,
            effective_on=effective_on,
            policy_area=CATEGORY_POLICY_AREA[plan.category],
            location_reference=location_reference,
            service_reference=service_reference,
            limit=5,
        )
        async with self.database.session() as session:
            search_result = await search_policy(session, request, self.embedding_provider)
            details = []
            for hit in search_result.data[:2]:
                detail = await fetch_policy_section(
                    session,
                    PolicySectionFetchInput(
                        section_id=hit.section_id,
                        effective_on=effective_on,
                        location_reference=location_reference,
                        service_reference=service_reference,
                    ),
                )
                details.append(detail.data.model_dump(mode="json"))

        ranked = [hit.model_dump(mode="json") for hit in search_result.data]
        available_ids = {hit.section_id for hit in search_result.data}
        invocation = await self._model_call(
            stage="policy_assessment",
            schema=PolicyAssessmentOutput,
            system_prompt=POLICY_AGENT_PROMPT,
            payload={
                "category": plan.category,
                "complaint": state["complaint_text"],
                "evidence": state.get("evidence", []),
                "allowed_section_ids": sorted(available_ids),
                "ranked_sections": ranked,
                "expanded_sections": details,
            },
        )
        assessment = cast(PolicyAssessmentOutput, invocation.value)
        if not assessment.selected_section_ids or not set(assessment.selected_section_ids).issubset(
            available_ids
        ):
            assessment = PolicyAssessmentOutput(
                applicable=False,
                selected_section_ids=[],
                rule_summary="The model did not select only retrieved policy sections.",
            )
        output = {
            "policy_results": ranked,
            "policy_assessment": assessment.model_dump(mode="json"),
            "input_tokens": state.get("input_tokens", 0) + invocation.input_tokens,
            "output_tokens": state.get("output_tokens", 0) + invocation.output_tokens,
        }
        if not assessment.applicable:
            output["escalation_reason"] = "applicable_policy_not_established"

        async with self.database.transaction() as session:
            await persist_policy_retrieval(
                session,
                case_run_id=run_id,
                query=plan.policy_query,
                effective_on=datetime.combine(effective_on, datetime.min.time(), UTC),
                filters={
                    "policy_area": CATEGORY_POLICY_AREA[plan.category],
                    "location_reference": location_reference,
                    "service_reference": service_reference,
                },
                results=ranked,
                selected_ids=assessment.selected_section_ids,
            )
            return await complete_stage(
                session, case_run_id=run_id, stage_name="policy", output=output
            )

    async def supplemental_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        stage_name = "supplemental_evidence_1"
        async with self.database.session() as session:
            cached = await completed_stage_output(session, run_id, stage_name)
        if cached is not None:
            return cached

        assessment = PolicyAssessmentOutput.model_validate(state["policy_assessment"])
        call = assessment.supplemental_call
        if call is None or state.get("supplemental_count", 0) >= 1:
            output: dict[str, Any] = {
                "escalation_reason": "supplemental_evidence_limit_or_request_invalid"
            }
            records: list[EvidenceRecord] = []
        else:
            async with self.database.session() as session:
                record = await self._execute_call(
                    session, call, customer_reference=state.get("customer_reference")
                )
            records = [record]
            combined = [*state.get("evidence", []), record.model_dump(mode="json")]
            output = {"evidence": combined, "supplemental_count": 1}
            if record.condition != "present":
                output["escalation_reason"] = "required_supplemental_evidence_missing"

        async with self.database.transaction() as session:
            await persist_evidence(session, case_run_id=run_id, records=records)
            return await complete_stage(
                session, case_run_id=run_id, stage_name=stage_name, output=output
            )

    async def proposal_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        async with self.database.session() as session:
            cached = await completed_stage_output(session, run_id, "resolution_proposal")
        if cached is not None:
            return cached

        allowed_evidence = {
            reference
            for item in state.get("evidence", [])
            for reference in item.get("source_references", [])
        }
        allowed_policy = set(
            PolicyAssessmentOutput.model_validate(state["policy_assessment"]).selected_section_ids
        )
        invocation = await self._model_call(
            stage="resolution_proposal",
            schema=ResolutionProposalOutput,
            system_prompt=CASE_MANAGER_PROPOSAL_PROMPT,
            payload={
                "complaint": state["complaint_text"],
                "plan": state["plan"],
                "evidence": state.get("evidence", []),
                "policy_assessment": state["policy_assessment"],
                "policy_results": state.get("policy_results", []),
                "allowed_evidence_references": sorted(allowed_evidence),
                "allowed_policy_references": sorted(allowed_policy),
            },
        )
        proposal = cast(ResolutionProposalOutput, invocation.value)
        if not set(proposal.evidence_references).issubset(allowed_evidence) or not set(
            proposal.policy_references
        ).issubset(allowed_policy):
            proposal = ResolutionProposalOutput(
                outcome="insufficient_grounding",
                disposition="human_investigation",
                rationale=(
                    "The proposed resolution cited evidence or policy outside the retrieved record."
                ),
                evidence_references=[],
                policy_references=[],
            )

        input_tokens = state.get("input_tokens", 0) + invocation.input_tokens
        output_tokens = state.get("output_tokens", 0) + invocation.output_tokens
        output = {
            "proposal": proposal.model_dump(mode="json"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        async with self.database.transaction() as session:
            await persist_proposal(session, case_run_id=run_id, proposal=proposal)
            return await complete_stage(
                session,
                case_run_id=run_id,
                stage_name="resolution_proposal",
                output=output,
            )

    async def preverification_node(self, state: CaseResolutionState) -> dict[str, Any]:
        result = _preverify(state)
        output: dict[str, Any] = {"preverification": result}
        if not result["passed"]:
            output["escalation_reason"] = "deterministic_preverification_failed"
        return output

    async def verifier_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        async with self.database.session() as session:
            cached = await completed_stage_output(session, run_id, "verification")
        if cached is not None:
            return cached
        invocation = await self._model_call(
            stage="verification",
            schema=VerificationOutput,
            system_prompt=VERIFIER_PROMPT,
            payload={
                "complaint": state["complaint_text"],
                "operational_source_records": state.get("evidence", []),
                "policy_source_records": state.get("policy_results", []),
                "policy_assessment": state["policy_assessment"],
                "proposal": state["proposal"],
            },
        )
        verification = cast(VerificationOutput, invocation.value)
        output = {
            "verification": verification.model_dump(mode="json"),
            "input_tokens": state.get("input_tokens", 0) + invocation.input_tokens,
            "output_tokens": state.get("output_tokens", 0) + invocation.output_tokens,
        }
        async with self.database.transaction() as session:
            await persist_verification(session, case_run_id=run_id, result=verification)
            return await complete_stage(
                session, case_run_id=run_id, stage_name="verification", output=output
            )

    async def disposition_node(self, state: CaseResolutionState) -> dict[str, Any]:
        proposal = ResolutionProposalOutput.model_validate(state["proposal"])
        verification = VerificationOutput.model_validate(state["verification"])
        if not verification.supported or any(
            [
                verification.missing_evidence,
                verification.contradictions,
                verification.unsupported_claims,
            ]
        ):
            return {
                "final_disposition": "human_investigation",
                "escalation_reason": "verifier_rejected_proposal",
            }
        if proposal.action_payload is not None:
            return {"final_disposition": "human_approval"}
        if proposal.disposition == "human_investigation":
            return {
                "final_disposition": "human_investigation",
                "escalation_reason": "case_manager_requested_investigation",
            }
        return {"final_disposition": "auto_resolve"}

    async def action_intent_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        case_id = _uuid(state["case_id"])
        proposal = ResolutionProposalOutput.model_validate(state["proposal"])
        assert proposal.action_payload is not None
        try:
            async with self.database.transaction() as session:
                intent = await create_action_intent(
                    session,
                    case_id=case_id,
                    case_run_id=run_id,
                    action_payload=proposal.action_payload.model_dump(mode="json"),
                )
                output = {"action_intent_reference": intent.public_reference}
                return await complete_stage(
                    session,
                    case_run_id=run_id,
                    stage_name="action_intent",
                    output=output,
                )
        except ActionValidationError:
            return {"escalation_reason": "action_intent_validation_failed"}

    async def approval_gate_node(self, state: CaseResolutionState) -> dict[str, Any]:
        action_reference = state["action_intent_reference"]
        async with self.database.session() as session:
            decision = await session.scalar(
                select(Approval.decision)
                .join(ActionIntent, ActionIntent.id == Approval.action_intent_id)
                .where(ActionIntent.public_reference == action_reference)
            )
        if decision is None:
            interrupt(
                {
                    "kind": "human_approval_required",
                    "case_reference": state["case_reference"],
                    "action_intent_reference": action_reference,
                }
            )
            async with self.database.session() as session:
                decision = await session.scalar(
                    select(Approval.decision)
                    .join(ActionIntent, ActionIntent.id == Approval.action_intent_id)
                    .where(ActionIntent.public_reference == action_reference)
                )
        if decision not in {"approved", "rejected"}:
            raise RuntimeError("approval resume occurred without a durable decision")
        output: dict[str, Any] = {"approval_decision": decision}
        if decision == "rejected":
            output["escalation_reason"] = "action_rejected_by_operations"
        return output

    async def execution_node(self, state: CaseResolutionState) -> dict[str, Any]:
        async with self.database.transaction() as session:
            result = await execute_approved_action(
                session, action_reference=state["action_intent_reference"]
            )
        if result.status != "succeeded":
            return {
                "escalation_reason": result.error_code or "action_execution_failed",
                "execution_receipt": result.receipt,
            }
        return {"execution_receipt": result.receipt}

    async def resolution_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        case_id = _uuid(state["case_id"])
        proposal = ResolutionProposalOutput.model_validate(state["proposal"])
        receipt = state.get("execution_receipt")
        if receipt:
            if receipt.get("action_type") == "refund_payment":
                response = f"We approved and completed a refund of {receipt['amount_cents']} cents."
            else:
                response = (
                    "We approved and completed a membership credit adjustment of "
                    f"{receipt['credit_delta']} credit(s)."
                )
        else:
            response = (
                "We reviewed your case against the verified account records and the policy "
                "that applied at the time. No account change was required, and the case is now "
                "complete."
            )
        output = {"customer_response": response}
        async with self.database.transaction() as session:
            cached = await completed_stage_output(session, run_id, "resolution")
            if cached is not None:
                return cached
            support_case = await session.get(SupportCase, case_id)
            if support_case is not None and support_case.status in {
                CaseStatus.PROCESSING.value,
                CaseStatus.PENDING_APPROVAL.value,
            }:
                resolved_case = await transition_case(
                    session,
                    case_id=case_id,
                    to_status=CaseStatus.RESOLVED,
                    event_type="case_resolved",
                    actor_type="system",
                    actor_reference="resolution_engine",
                    payload={
                        "outcome": proposal.outcome,
                        "customer_response": response,
                        "execution_receipt": receipt or {},
                    },
                )
                await prepare_final_email(
                    session,
                    support_case=resolved_case,
                    customer_response=response,
                    execution_receipt=receipt,
                )
            await complete_run(
                session,
                run_id,
                input_tokens=state.get("input_tokens", 0),
                output_tokens=state.get("output_tokens", 0),
            )
            return await complete_stage(
                session, case_run_id=run_id, stage_name="resolution", output=output
            )

    async def escalation_node(self, state: CaseResolutionState) -> dict[str, Any]:
        run_id = _uuid(state["case_run_id"])
        case_id = _uuid(state["case_id"])
        reason = state.get("escalation_reason") or "agent_workflow_unsupported"
        output = {"escalation_reason": reason}
        async with self.database.transaction() as session:
            cached = await completed_stage_output(session, run_id, "human_investigation")
            if cached is not None:
                return cached
            exists = await session.scalar(
                select(Escalation.id).where(
                    Escalation.case_id == case_id,
                    Escalation.case_run_id == run_id,
                )
            )
            if exists is None:
                session.add(
                    Escalation(
                        case_id=case_id,
                        case_run_id=run_id,
                        reason_code=reason,
                        details={"case_run_id": str(run_id)},
                        status="open",
                    )
                )
            support_case = await session.get(SupportCase, case_id)
            if support_case is not None and support_case.status in {
                CaseStatus.QUEUED.value,
                CaseStatus.PROCESSING.value,
                CaseStatus.PENDING_APPROVAL.value,
            }:
                await transition_case(
                    session,
                    case_id=case_id,
                    to_status=CaseStatus.HUMAN_INVESTIGATION,
                    event_type="agent_escalated",
                    actor_type="agent",
                    actor_reference="case_manager",
                    payload={"reason_code": reason, "case_run_id": str(run_id)},
                )
            await complete_run(
                session,
                run_id,
                input_tokens=state.get("input_tokens", 0),
                output_tokens=state.get("output_tokens", 0),
            )
            return await complete_stage(
                session,
                case_run_id=run_id,
                stage_name="human_investigation",
                output=output,
            )

    @staticmethod
    def _after_plan(state: CaseResolutionState) -> Literal["investigation", "escalation"]:
        return "escalation" if state.get("escalation_reason") else "investigation"

    @staticmethod
    def _after_gate(state: CaseResolutionState) -> Literal["policy", "escalation"]:
        return "escalation" if state.get("escalation_reason") else "policy"

    @staticmethod
    def _after_policy(
        state: CaseResolutionState,
    ) -> Literal["supplemental", "proposal", "escalation"]:
        if state.get("escalation_reason"):
            return "escalation"
        assessment = PolicyAssessmentOutput.model_validate(state["policy_assessment"])
        if assessment.missing_evidence_types:
            return "supplemental" if assessment.supplemental_call is not None else "escalation"
        return "proposal"

    @staticmethod
    def _after_supplemental(state: CaseResolutionState) -> Literal["proposal", "escalation"]:
        return "escalation" if state.get("escalation_reason") else "proposal"

    @staticmethod
    def _after_preverification(state: CaseResolutionState) -> Literal["verifier", "escalation"]:
        return "escalation" if state.get("escalation_reason") else "verifier"

    @staticmethod
    def _after_disposition(
        state: CaseResolutionState,
    ) -> Literal["action_intent", "resolution", "escalation"]:
        if state.get("final_disposition") == "human_approval":
            return "action_intent"
        if state.get("final_disposition") == "auto_resolve":
            return "resolution"
        return "escalation"

    @staticmethod
    def _after_action_intent(state: CaseResolutionState) -> Literal["approval_gate", "escalation"]:
        return "escalation" if state.get("escalation_reason") else "approval_gate"

    @staticmethod
    def _after_approval(state: CaseResolutionState) -> Literal["execution", "escalation"]:
        if state.get("approval_decision") == "approved":
            return "execution"
        return "escalation"

    @staticmethod
    def _after_execution(state: CaseResolutionState) -> Literal["resolution", "escalation"]:
        return "escalation" if state.get("escalation_reason") else "resolution"

    def compile(self, *, checkpointer: BaseCheckpointSaver[Any] | None = None) -> Any:
        graph = StateGraph(CaseResolutionState)
        graph.add_node("plan", self.plan_node)
        graph.add_node("investigation", self.investigation_node)
        graph.add_node("evidence_gate", self.evidence_gate_node)
        graph.add_node("policy", self.policy_node)
        graph.add_node("supplemental", self.supplemental_node)
        graph.add_node("proposal", self.proposal_node)
        graph.add_node("preverification", self.preverification_node)
        graph.add_node("verifier", self.verifier_node)
        graph.add_node("disposition", self.disposition_node)
        graph.add_node("action_intent", self.action_intent_node)
        graph.add_node("approval_gate", self.approval_gate_node)
        graph.add_node("execution", self.execution_node)
        graph.add_node("resolution", self.resolution_node)
        graph.add_node("escalation", self.escalation_node)
        graph.add_edge(START, "plan")
        graph.add_conditional_edges("plan", self._after_plan)
        graph.add_edge("investigation", "evidence_gate")
        graph.add_conditional_edges("evidence_gate", self._after_gate)
        graph.add_conditional_edges("policy", self._after_policy)
        graph.add_conditional_edges("supplemental", self._after_supplemental)
        graph.add_edge("proposal", "preverification")
        graph.add_conditional_edges("preverification", self._after_preverification)
        graph.add_edge("verifier", "disposition")
        graph.add_conditional_edges("disposition", self._after_disposition)
        graph.add_conditional_edges("action_intent", self._after_action_intent)
        graph.add_conditional_edges("approval_gate", self._after_approval)
        graph.add_conditional_edges("execution", self._after_execution)
        graph.add_edge("resolution", END)
        graph.add_edge("escalation", END)
        return graph.compile(checkpointer=checkpointer)
