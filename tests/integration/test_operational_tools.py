from __future__ import annotations

from datetime import UTC, datetime

import pytest

from luma.agents.contracts import GetAppointmentTimelineCall
from luma.agents.tool_executor import execute_operational_call
from luma.tools.contracts import (
    AppointmentEvidenceInput,
    BookingAttemptEvidenceInput,
    CustomerAppointmentsInput,
    CustomerBookingAttemptsInput,
    CustomerRefInput,
    MembershipEvidenceInput,
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

pytestmark = pytest.mark.integration


async def test_executor_injects_trusted_customer_scope_when_model_omits_it(database) -> None:
    async with database.session() as session:
        evidence = await execute_operational_call(
            session,
            GetAppointmentTimelineCall(
                tool_name="get_appointment_timeline",
                arguments={"appointment_reference": "APPT-CAN-PROVIDER"},
                purpose="Inspect cancellation history.",
            ),
            expected_customer_reference="CUS-0001",
        )

    assert evidence.condition == "present"
    assert "APPT-CAN-PROVIDER" in evidence.source_references


async def test_executor_rejects_model_attempt_to_change_customer_scope(database) -> None:
    async with database.session() as session:
        evidence = await execute_operational_call(
            session,
            GetAppointmentTimelineCall(
                tool_name="get_appointment_timeline",
                arguments={
                    "customer_reference": "CUS-0002",
                    "appointment_reference": "APPT-CAN-PROVIDER",
                },
                purpose="Inspect another customer's history.",
            ),
            expected_customer_reference="CUS-0001",
        )

    assert evidence.condition == "contradictory"
    assert evidence.tool_call_id is None


async def test_customer_and_appointment_list_are_masked_bounded_and_provenanced(database) -> None:
    async with database.session() as session:
        customer = await get_customer(session, CustomerRefInput(customer_reference="CUS-0001"))
        appointments = await get_customer_appointments(
            session,
            CustomerAppointmentsInput(customer_reference="CUS-0001", limit=2),
        )

    assert customer.data.masked_email is None or "***@" in customer.data.masked_email
    assert customer.data.masked_phone is None or customer.data.masked_phone.startswith("***")
    assert len(appointments.data) == 2
    assert appointments.metadata.truncated is True
    assert all(item.customer_reference == "CUS-0001" for item in appointments.data)
    assert all(item.employee_reference.startswith("EMP-") for item in appointments.data)


async def test_appointment_timeline_returns_authoritative_provider_cancellation(database) -> None:
    async with database.session() as session:
        result = await get_appointment_timeline(
            session,
            AppointmentEvidenceInput(
                customer_reference="CUS-0001",
                appointment_reference="APPT-CAN-PROVIDER",
            ),
        )

    cancellation = next(
        event for event in result.data.events if event.event_type == "appointment_cancelled"
    )
    assert cancellation.initiating_party == "provider"
    assert cancellation.reason_code == "provider_unavailable"
    assert cancellation.provenance.source_reference == cancellation.event_reference
    assert result.data.successor_appointments == []
    assert result.metadata.tool_call_id.startswith("TOOL-")


async def test_cross_customer_appointment_lookup_does_not_reveal_record(database) -> None:
    async with database.session() as session:
        with pytest.raises(EntityNotFoundError, match="not found for this customer"):
            await get_appointment_timeline(
                session,
                AppointmentEvidenceInput(
                    customer_reference="CUS-0002",
                    appointment_reference="APPT-CAN-PROVIDER",
                ),
            )


async def test_duplicate_payment_tool_returns_both_captures_and_shared_obligation(database) -> None:
    async with database.session() as session:
        result = await get_appointment_payments(
            session,
            AppointmentEvidenceInput(
                customer_reference="CUS-0007", appointment_reference="APPT-DUP-PAY"
            ),
        )

    captures = [payment for payment in result.data.payments if payment.status == "captured"]
    assert len(captures) == 2
    assert len({payment.obligation_reference for payment in captures}) == 1
    assert all(payment.captured_amount_cents == 12000 for payment in captures)


async def test_membership_tool_exposes_duplicate_consumption_and_derived_balance(database) -> None:
    async with database.session() as session:
        result = await get_membership_evidence(
            session,
            MembershipEvidenceInput(
                customer_reference="CUS-0001",
                as_of=datetime(2026, 9, 1, tzinfo=UTC),
            ),
        )

    duplicate_consumptions = [
        entry
        for entry in result.data.ledger
        if entry.related_appointment_reference == "APPT-MEM-DUP" and entry.entry_type == "consume"
    ]
    assert len(duplicate_consumptions) == 2
    assert all(entry.allocations for entry in duplicate_consumptions)
    assert result.data.derived_balance == sum(entry.credit_delta for entry in result.data.ledger)


async def test_booking_tool_returns_attempt_and_effective_configuration(database) -> None:
    async with database.session() as session:
        result = await get_booking_attempt_evidence(
            session,
            BookingAttemptEvidenceInput(
                customer_reference="CUS-0020",
                booking_attempt_reference="BATT-PROVIDER-OVERRIDE",
            ),
        )

    assert result.data.reason_code == "employee_online_disabled"
    employee_fact = next(
        fact
        for fact in result.data.configuration_facts
        if fact.fact_type == "employee_booking_setting"
    )
    assert employee_fact.value["online_enabled"] is False


async def test_booking_attempts_can_be_discovered_from_customer_and_time_window(database) -> None:
    async with database.session() as session:
        result = await get_customer_booking_attempts(
            session,
            CustomerBookingAttemptsInput(
                customer_reference="CUS-0020",
                starts_on_or_after=datetime(2026, 9, 1, tzinfo=UTC),
                starts_before=datetime(2026, 10, 1, tzinfo=UTC),
            ),
        )

    assert any(
        attempt.booking_attempt_reference == "BATT-PROVIDER-OVERRIDE" for attempt in result.data
    )


@pytest.mark.parametrize(
    ("customer_reference", "attempt_reference", "fact_type", "expected_condition"),
    [
        ("CUS-0021", "BATT-NO-QUALIFICATION", "employee_service_qualification", "known_absent"),
        ("CUS-0022", "BATT-OUTSIDE-SCHEDULE", "employee_schedule_coverage", "known_absent"),
        ("CUS-0023", "BATT-LOCATION-CLOSED", "location_business_hours", "known_absent"),
    ],
)
async def test_booking_context_exposes_evidence_behind_rejection(
    database,
    customer_reference: str,
    attempt_reference: str,
    fact_type: str,
    expected_condition: str,
) -> None:
    async with database.session() as session:
        result = await get_booking_attempt_evidence(
            session,
            BookingAttemptEvidenceInput(
                customer_reference=customer_reference,
                booking_attempt_reference=attempt_reference,
            ),
        )

    fact = next(item for item in result.data.configuration_facts if item.fact_type == fact_type)
    assert fact.condition == expected_condition
