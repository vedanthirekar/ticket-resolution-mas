from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from luma.agents.contracts import EvidenceRecord, OperationalCall
from luma.tools.contracts import (
    AppointmentEvidenceInput,
    BookingAttemptEvidenceInput,
    CustomerAppointmentsInput,
    CustomerBookingAttemptsInput,
    CustomerRefInput,
    MembershipEvidenceInput,
    ToolResult,
)
from luma.tools.errors import EntityNotFoundError
from luma.tools.operational import (
    get_appointment_payments,
    get_appointment_timeline,
    get_booking_attempt_evidence,
    get_customer,
    get_customer_appointments,
    get_customer_booking_attempts,
    get_membership_evidence,
)

ToolFunction = Callable[[AsyncSession, Any], Awaitable[ToolResult[Any]]]

TOOL_REGISTRY: dict[str, tuple[type[BaseModel], ToolFunction, str]] = {
    "get_customer": (CustomerRefInput, cast(ToolFunction, get_customer), "customer_identity"),
    "get_customer_appointments": (
        CustomerAppointmentsInput,
        cast(ToolFunction, get_customer_appointments),
        "booking_history",
    ),
    "get_appointment_timeline": (
        AppointmentEvidenceInput,
        cast(ToolFunction, get_appointment_timeline),
        "appointment_timeline",
    ),
    "get_appointment_payments": (
        AppointmentEvidenceInput,
        cast(ToolFunction, get_appointment_payments),
        "payment",
    ),
    "get_membership_evidence": (
        MembershipEvidenceInput,
        cast(ToolFunction, get_membership_evidence),
        "membership_ledger",
    ),
    "get_customer_booking_attempts": (
        CustomerBookingAttemptsInput,
        cast(ToolFunction, get_customer_booking_attempts),
        "booking_history",
    ),
    "get_booking_attempt_evidence": (
        BookingAttemptEvidenceInput,
        cast(ToolFunction, get_booking_attempt_evidence),
        "booking_configuration",
    ),
}


def _collect_source_references(value: Any) -> list[str]:
    references: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            provenance = item.get("provenance")
            if isinstance(provenance, dict) and isinstance(provenance.get("source_reference"), str):
                references.add(provenance["source_reference"])
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return sorted(references)


def _detect_condition(evidence_type: str, content: dict[str, Any]) -> str:
    data = content.get("data")
    if isinstance(data, list) and not data:
        return "known_absent"
    if evidence_type == "payment" and isinstance(data, dict) and not data.get("payments"):
        return "known_absent"
    if evidence_type == "appointment_timeline" and isinstance(data, dict):
        appointment = data.get("appointment", {})
        events = data.get("events", [])
        if isinstance(appointment, dict) and appointment.get("status") in {"cancelled", "no_show"}:
            terminal_events = {
                event.get("initiating_party")
                for event in events
                if isinstance(event, dict)
                and event.get("event_type") in {"appointment_cancelled", "appointment_no_show"}
            }
            terminal_events.discard(None)
            if not terminal_events:
                return "missing"
            if len(terminal_events) > 1:
                return "contradictory"
    return "present"


async def execute_operational_call(
    session: AsyncSession,
    call: OperationalCall,
    *,
    expected_customer_reference: str | None,
) -> EvidenceRecord:
    request_type, function, evidence_type = TOOL_REGISTRY[call.tool_name]
    arguments = dict(call.arguments)
    supplied_customer = arguments.get("customer_reference")
    if expected_customer_reference is None:
        return EvidenceRecord(
            evidence_type=evidence_type,
            condition="missing",
            tool_name=call.tool_name,
            error="customer identity is not established",
        )
    if supplied_customer is not None and supplied_customer != expected_customer_reference:
        return EvidenceRecord(
            evidence_type=evidence_type,
            condition="contradictory",
            tool_name=call.tool_name,
            error="tool customer_reference does not match the case customer",
        )

    # Customer scope comes from the authenticated case context, not model output. The
    # model may omit it, but it may never override it with another customer's reference.
    arguments["customer_reference"] = expected_customer_reference

    try:
        request = request_type.model_validate(arguments)
        result = await function(session, request)
    except (EntityNotFoundError, ValueError) as exc:
        return EvidenceRecord(
            evidence_type=evidence_type,
            condition="missing",
            tool_name=call.tool_name,
            error=str(exc),
        )

    serialized = result.model_dump(mode="json")
    return EvidenceRecord(
        evidence_type=evidence_type,
        condition=cast(Any, _detect_condition(evidence_type, serialized)),
        tool_name=call.tool_name,
        tool_call_id=result.metadata.tool_call_id,
        source_references=_collect_source_references(serialized),
        content=serialized,
    )
