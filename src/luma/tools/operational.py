from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from luma.db.models.appointment import Appointment, AppointmentEvent
from luma.db.models.billing import Invoice, InvoiceItem, Payment, PaymentEvent, Refund
from luma.db.models.booking import (
    BookingAttempt,
    BookingBlock,
    BookingSetting,
    EmployeeBookingSetting,
    LocationResource,
    LocationServiceSetting,
)
from luma.db.models.membership import (
    Membership,
    MembershipCreditAllocation,
    MembershipLedgerEntry,
    MembershipPlan,
)
from luma.db.models.organization import (
    Customer,
    Employee,
    EmployeeLocation,
    EmployeeSchedule,
    EmployeeService,
    Location,
    LocationBusinessHours,
    LocationService,
    Service,
)
from luma.tools.contracts import (
    AppointmentEventEvidence,
    AppointmentEvidenceInput,
    AppointmentPayments,
    AppointmentSummary,
    AppointmentTimeline,
    BookingAttemptEvidence,
    BookingAttemptEvidenceInput,
    BookingAttemptSummary,
    ConfigurationFact,
    CustomerAppointmentsInput,
    CustomerBookingAttemptsInput,
    CustomerEvidence,
    CustomerRefInput,
    InvoiceItemEvidence,
    LedgerAllocationEvidence,
    MembershipEvidence,
    MembershipEvidenceInput,
    MembershipLedgerEvidence,
    PaymentEventEvidence,
    PaymentEvidence,
    Provenance,
    RefundEvidence,
    ToolMetadata,
    ToolResult,
)
from luma.tools.errors import EntityNotFoundError, InvalidToolRequestError


def _metadata(tool_name: str, count: int, *, truncated: bool = False) -> ToolMetadata:
    return ToolMetadata(
        tool_call_id=f"TOOL-{uuid4().hex}",
        tool_name=tool_name,
        executed_at=datetime.now(UTC),
        result_count=count,
        truncated=truncated,
    )


def _provenance(table: str, reference: str) -> Provenance:
    return Provenance(source_table=f"business.{table}", source_reference=reference)


def _mask_email(value: str | None) -> str | None:
    if value is None:
        return None
    local, separator, domain = value.partition("@")
    if not separator:
        return "***"
    return f"{local[:1]}***@{domain}"


def _mask_phone(value: str | None) -> str | None:
    if value is None:
        return None
    return f"***{value[-4:]}"


async def _customer(session: AsyncSession, reference: str) -> Customer:
    customer = await session.scalar(select(Customer).where(Customer.public_reference == reference))
    if customer is None:
        raise EntityNotFoundError("customer was not found")
    return customer


async def get_customer(
    session: AsyncSession, request: CustomerRefInput
) -> ToolResult[CustomerEvidence]:
    customer = await _customer(session, request.customer_reference)
    data = CustomerEvidence(
        customer_reference=customer.public_reference,
        display_name=f"{customer.first_name} {customer.last_name}",
        masked_email=_mask_email(customer.email),
        masked_phone=_mask_phone(customer.phone),
        email_verified=customer.email_verified,
        phone_verified=customer.phone_verified,
        active=customer.active,
        provenance=_provenance("customers", customer.public_reference),
    )
    return ToolResult(metadata=_metadata("get_customer", 1), data=data)


def _appointment_summary(
    row: tuple[Appointment, str, str, str, str, str | None, str],
) -> AppointmentSummary:
    (
        appointment,
        customer_ref,
        location_ref,
        service_ref,
        service_name,
        predecessor_ref,
        employee_ref,
    ) = row
    return AppointmentSummary(
        appointment_reference=appointment.public_reference,
        customer_reference=customer_ref,
        location_reference=location_ref,
        service_reference=service_ref,
        service_name=service_name,
        employee_reference=employee_ref,
        scheduled_start=appointment.scheduled_start,
        scheduled_end=appointment.scheduled_end,
        status=appointment.status,
        quoted_price_cents=appointment.quoted_price_cents,
        quoted_credit_cost=appointment.quoted_credit_cost,
        currency=appointment.currency,
        booking_channel=appointment.booking_channel,
        predecessor_appointment_reference=predecessor_ref,
        provenance=_provenance("appointments", appointment.public_reference),
    )


def _appointment_query() -> Select[tuple[Appointment, str, str, str, str, str | None, str]]:
    predecessor = Appointment.__table__.alias("predecessor")
    return (
        select(
            Appointment,
            Customer.public_reference,
            Location.public_reference,
            Service.public_reference,
            Service.name,
            predecessor.c.public_reference,
            Employee.public_reference,
        )
        .join(Customer, Customer.id == Appointment.customer_id)
        .join(Location, Location.id == Appointment.location_id)
        .join(Service, Service.id == Appointment.service_id)
        .join(Employee, Employee.id == Appointment.employee_id)
        .outerjoin(predecessor, predecessor.c.id == Appointment.predecessor_appointment_id)
    )


async def get_customer_appointments(
    session: AsyncSession, request: CustomerAppointmentsInput
) -> ToolResult[list[AppointmentSummary]]:
    customer = await _customer(session, request.customer_reference)
    if (
        request.starts_on_or_after is not None
        and request.starts_before is not None
        and request.starts_before <= request.starts_on_or_after
    ):
        raise InvalidToolRequestError("starts_before must be after starts_on_or_after")
    statement = _appointment_query().where(Appointment.customer_id == customer.id)
    if request.starts_on_or_after is not None:
        statement = statement.where(Appointment.scheduled_start >= request.starts_on_or_after)
    if request.starts_before is not None:
        statement = statement.where(Appointment.scheduled_start < request.starts_before)
    rows = (
        await session.execute(
            statement.order_by(Appointment.scheduled_start.desc()).limit(request.limit + 1)
        )
    ).all()
    truncated = len(rows) > request.limit
    summaries = [
        _appointment_summary(_normalize_appointment_row(row)) for row in rows[: request.limit]
    ]
    return ToolResult(
        metadata=_metadata("get_customer_appointments", len(summaries), truncated=truncated),
        data=summaries,
    )


def _normalize_appointment_row(
    row: Any,
) -> tuple[Appointment, str, str, str, str, str | None, str]:
    values = tuple(row)
    return (
        cast(Appointment, values[0]),
        cast(str, values[1]),
        cast(str, values[2]),
        cast(str, values[3]),
        cast(str, values[4]),
        cast(str | None, values[5]),
        cast(str, values[6]),
    )


async def _owned_appointment(
    session: AsyncSession, request: AppointmentEvidenceInput
) -> tuple[Appointment, str, str, str, str, str | None, str]:
    row = (
        await session.execute(
            _appointment_query().where(
                Appointment.public_reference == request.appointment_reference,
                Customer.public_reference == request.customer_reference,
            )
        )
    ).one_or_none()
    if row is None:
        raise EntityNotFoundError("appointment was not found for this customer")
    return _normalize_appointment_row(row)


async def get_appointment_timeline(
    session: AsyncSession, request: AppointmentEvidenceInput
) -> ToolResult[AppointmentTimeline]:
    row = await _owned_appointment(session, request)
    appointment = row[0]
    event_rows = (
        await session.execute(
            select(AppointmentEvent)
            .where(AppointmentEvent.appointment_id == appointment.id)
            .order_by(AppointmentEvent.occurred_at, AppointmentEvent.id)
        )
    ).scalars()
    events = [
        AppointmentEventEvidence(
            event_reference=event.public_reference,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_reference=event.actor_reference,
            initiating_party=event.initiating_party,
            reason_code=event.reason_code,
            occurred_at=event.occurred_at,
            recorded_at=event.recorded_at,
            channel=event.channel,
            correlation_reference=event.correlation_reference,
            event_metadata=event.event_metadata,
            provenance=_provenance("appointment_events", event.public_reference),
        )
        for event in event_rows
    ]
    successor_rows = (
        await session.execute(
            _appointment_query()
            .where(
                Appointment.predecessor_appointment_id == appointment.id,
                Appointment.customer_id == appointment.customer_id,
            )
            .order_by(Appointment.scheduled_start)
        )
    ).all()
    successors = [
        _appointment_summary(_normalize_appointment_row(successor_row))
        for successor_row in successor_rows
    ]
    timeline = AppointmentTimeline(
        appointment=_appointment_summary(row),
        events=events,
        successor_appointments=successors,
    )
    return ToolResult(
        metadata=_metadata("get_appointment_timeline", 1 + len(events) + len(successors)),
        data=timeline,
    )


async def get_appointment_payments(
    session: AsyncSession, request: AppointmentEvidenceInput
) -> ToolResult[AppointmentPayments]:
    appointment_row = await _owned_appointment(session, request)
    appointment = appointment_row[0]
    invoices = (
        (
            await session.execute(
                select(Invoice)
                .outerjoin(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
                .where(
                    Invoice.customer_id == appointment.customer_id,
                    or_(
                        Invoice.appointment_id == appointment.id,
                        InvoiceItem.appointment_id == appointment.id,
                    ),
                )
                .distinct()
                .order_by(Invoice.created_at)
            )
        )
        .scalars()
        .all()
    )
    evidence: list[PaymentEvidence] = []
    for invoice in invoices:
        items = (
            (
                await session.execute(
                    select(InvoiceItem)
                    .where(InvoiceItem.invoice_id == invoice.id)
                    .order_by(InvoiceItem.created_at, InvoiceItem.id)
                )
            )
            .scalars()
            .all()
        )
        payments = (
            (
                await session.execute(
                    select(Payment)
                    .where(Payment.invoice_id == invoice.id)
                    .order_by(Payment.created_at, Payment.id)
                )
            )
            .scalars()
            .all()
        )
        for payment in payments:
            events = (
                (
                    await session.execute(
                        select(PaymentEvent)
                        .where(PaymentEvent.payment_id == payment.id)
                        .order_by(PaymentEvent.occurred_at, PaymentEvent.id)
                    )
                )
                .scalars()
                .all()
            )
            refunds = (
                (
                    await session.execute(
                        select(Refund)
                        .where(Refund.payment_id == payment.id)
                        .order_by(Refund.created_at, Refund.id)
                    )
                )
                .scalars()
                .all()
            )
            evidence.append(
                PaymentEvidence(
                    payment_reference=payment.public_reference,
                    invoice_reference=invoice.public_reference,
                    obligation_reference=payment.obligation_reference,
                    status=payment.status,
                    tender_type=payment.tender_type,
                    amount_cents=payment.amount_cents,
                    authorized_amount_cents=payment.authorized_amount_cents,
                    captured_amount_cents=payment.captured_amount_cents,
                    refunded_amount_cents=payment.refunded_amount_cents,
                    refundable_amount_cents=(
                        payment.captured_amount_cents - payment.refunded_amount_cents
                    ),
                    currency=payment.currency,
                    created_at=payment.created_at,
                    items=[
                        InvoiceItemEvidence(
                            item_reference=item.public_reference,
                            item_type=item.item_type,
                            description=item.description,
                            quantity=item.quantity,
                            amount_cents=item.amount_cents,
                            currency=item.currency,
                            provenance=_provenance("invoice_items", item.public_reference),
                        )
                        for item in items
                    ],
                    events=[
                        PaymentEventEvidence(
                            event_reference=event.public_reference,
                            event_type=event.event_type,
                            amount_cents=event.amount_cents,
                            occurred_at=event.occurred_at,
                            processor_event_reference=event.processor_event_reference,
                            provenance=_provenance("payment_events", event.public_reference),
                        )
                        for event in events
                    ],
                    refunds=[
                        RefundEvidence(
                            refund_reference=refund.public_reference,
                            amount_cents=refund.amount_cents,
                            status=refund.status,
                            reason_code=refund.reason_code,
                            completed_at=refund.completed_at,
                            provenance=_provenance("refunds", refund.public_reference),
                        )
                        for refund in refunds
                    ],
                    provenance=_provenance("payments", payment.public_reference),
                )
            )
    return ToolResult(
        metadata=_metadata("get_appointment_payments", len(evidence)),
        data=AppointmentPayments(
            appointment_reference=appointment.public_reference, payments=evidence
        ),
    )


async def get_membership_evidence(
    session: AsyncSession, request: MembershipEvidenceInput
) -> ToolResult[MembershipEvidence]:
    customer = await _customer(session, request.customer_reference)
    statement = (
        select(Membership, MembershipPlan)
        .join(MembershipPlan, MembershipPlan.id == Membership.plan_id)
        .where(Membership.customer_id == customer.id)
    )
    if request.membership_reference:
        statement = statement.where(Membership.public_reference == request.membership_reference)
    row = (
        await session.execute(statement.order_by(Membership.created_at.desc()).limit(1))
    ).one_or_none()
    if row is None:
        raise EntityNotFoundError("membership was not found for this customer")
    membership, plan = row
    ledger_rows = (
        (
            await session.execute(
                select(MembershipLedgerEntry)
                .where(
                    MembershipLedgerEntry.membership_id == membership.id,
                    MembershipLedgerEntry.effective_at <= request.as_of,
                )
                .order_by(MembershipLedgerEntry.effective_at, MembershipLedgerEntry.id)
                .limit(request.limit + 1)
            )
        )
        .scalars()
        .all()
    )
    if len(ledger_rows) > request.limit:
        raise InvalidToolRequestError(
            "membership ledger exceeds the requested bound; narrow the as_of interval"
        )
    appointment_rows = (
        await session.execute(
            select(Appointment.id, Appointment.public_reference).where(
                Appointment.id.in_(
                    [
                        entry.related_appointment_id
                        for entry in ledger_rows
                        if entry.related_appointment_id
                    ]
                )
            )
        )
    ).all()
    appointment_refs: dict[UUID, str] = {row[0]: row[1] for row in appointment_rows}
    entry_refs = {entry.id: entry.public_reference for entry in ledger_rows}
    ledger: list[MembershipLedgerEvidence] = []
    for entry in ledger_rows:
        allocation_rows = (
            await session.execute(
                select(MembershipCreditAllocation, MembershipLedgerEntry.public_reference)
                .join(
                    MembershipLedgerEntry,
                    MembershipLedgerEntry.id == MembershipCreditAllocation.grant_entry_id,
                )
                .where(MembershipCreditAllocation.consumption_entry_id == entry.id)
            )
        ).all()
        ledger.append(
            MembershipLedgerEvidence(
                ledger_reference=entry.public_reference,
                entry_type=entry.entry_type,
                credit_delta=entry.credit_delta,
                effective_at=entry.effective_at,
                expires_at=entry.expires_at,
                related_appointment_reference=(
                    appointment_refs.get(entry.related_appointment_id)
                    if entry.related_appointment_id is not None
                    else None
                ),
                related_entry_reference=(
                    entry_refs.get(entry.related_entry_id)
                    if entry.related_entry_id is not None
                    else None
                ),
                reason_code=entry.reason_code,
                approval_reference=entry.approval_reference,
                allocations=[
                    LedgerAllocationEvidence(
                        grant_entry_reference=grant_reference,
                        quantity=allocation.quantity,
                        provenance=Provenance(
                            source_table="business.membership_credit_allocations",
                            source_reference=str(allocation.id),
                        ),
                    )
                    for allocation, grant_reference in allocation_rows
                ],
                provenance=_provenance("membership_ledger", entry.public_reference),
            )
        )
    data = MembershipEvidence(
        membership_reference=membership.public_reference,
        customer_reference=customer.public_reference,
        plan_reference=plan.public_reference,
        plan_name=plan.name,
        status=membership.status,
        starts_at=membership.starts_at,
        ends_at=membership.ends_at,
        terms_policy_id=membership.terms_policy_id,
        terms_version=membership.terms_version,
        derived_balance=sum(entry.credit_delta for entry in ledger_rows),
        ledger=ledger,
        provenance=_provenance("memberships", membership.public_reference),
    )
    return ToolResult(metadata=_metadata("get_membership_evidence", 1 + len(ledger)), data=data)


async def get_customer_booking_attempts(
    session: AsyncSession, request: CustomerBookingAttemptsInput
) -> ToolResult[list[BookingAttemptSummary]]:
    customer = await _customer(session, request.customer_reference)
    if (
        request.starts_on_or_after is not None
        and request.starts_before is not None
        and request.starts_before <= request.starts_on_or_after
    ):
        raise InvalidToolRequestError("starts_before must be after starts_on_or_after")
    statement = (
        select(
            BookingAttempt,
            Location.public_reference,
            Service.public_reference,
            Employee.public_reference,
            Appointment.public_reference,
        )
        .join(Location, Location.id == BookingAttempt.location_id)
        .join(Service, Service.id == BookingAttempt.service_id)
        .outerjoin(Employee, Employee.id == BookingAttempt.requested_employee_id)
        .outerjoin(Appointment, Appointment.id == BookingAttempt.appointment_id)
        .where(BookingAttempt.customer_id == customer.id)
    )
    if request.starts_on_or_after is not None:
        statement = statement.where(BookingAttempt.requested_start >= request.starts_on_or_after)
    if request.starts_before is not None:
        statement = statement.where(BookingAttempt.requested_start < request.starts_before)
    rows = (
        await session.execute(
            statement.order_by(BookingAttempt.requested_start.desc()).limit(request.limit + 1)
        )
    ).all()
    truncated = len(rows) > request.limit
    data = [
        BookingAttemptSummary(
            booking_attempt_reference=attempt.public_reference,
            customer_reference=customer.public_reference,
            location_reference=location_ref,
            service_reference=service_ref,
            requested_employee_reference=employee_ref,
            requested_start=attempt.requested_start,
            status=attempt.status,
            reason_code=attempt.reason_code,
            committed_appointment_reference=appointment_ref,
            provenance=_provenance("booking_attempts", attempt.public_reference),
        )
        for attempt, location_ref, service_ref, employee_ref, appointment_ref in rows[
            : request.limit
        ]
    ]
    return ToolResult(
        metadata=_metadata("get_customer_booking_attempts", len(data), truncated=truncated),
        data=data,
    )


async def get_booking_attempt_evidence(
    session: AsyncSession, request: BookingAttemptEvidenceInput
) -> ToolResult[BookingAttemptEvidence]:
    row = (
        await session.execute(
            select(
                BookingAttempt,
                Customer.public_reference,
                Location.public_reference,
                Service.public_reference,
                Employee.public_reference,
                Appointment.public_reference,
            )
            .join(Customer, Customer.id == BookingAttempt.customer_id)
            .join(Location, Location.id == BookingAttempt.location_id)
            .join(Service, Service.id == BookingAttempt.service_id)
            .outerjoin(Employee, Employee.id == BookingAttempt.requested_employee_id)
            .outerjoin(Appointment, Appointment.id == BookingAttempt.appointment_id)
            .where(
                BookingAttempt.public_reference == request.booking_attempt_reference,
                Customer.public_reference == request.customer_reference,
            )
        )
    ).one_or_none()
    if row is None:
        raise EntityNotFoundError("booking attempt was not found for this customer")
    attempt, customer_ref, location_ref, service_ref, employee_ref, appointment_ref = row
    effective_date = attempt.requested_start.date()
    facts: list[ConfigurationFact] = []

    global_setting = await session.scalar(
        select(BookingSetting)
        .where(
            BookingSetting.effective_from <= effective_date,
            or_(
                BookingSetting.effective_through.is_(None),
                BookingSetting.effective_through >= effective_date,
            ),
        )
        .order_by(BookingSetting.effective_from.desc())
        .limit(1)
    )
    if global_setting:
        facts.append(
            ConfigurationFact(
                fact_type="global_booking_setting",
                value={
                    "minimum_lead_minutes": global_setting.minimum_lead_minutes,
                    "booking_horizon_days": global_setting.booking_horizon_days,
                },
                provenance=Provenance(
                    source_table="business.booking_settings",
                    source_reference=str(global_setting.id),
                ),
            )
        )
    location_setting = await session.scalar(
        select(LocationServiceSetting)
        .where(
            LocationServiceSetting.location_id == attempt.location_id,
            LocationServiceSetting.service_id == attempt.service_id,
            LocationServiceSetting.effective_from <= effective_date,
            or_(
                LocationServiceSetting.effective_through.is_(None),
                LocationServiceSetting.effective_through >= effective_date,
            ),
        )
        .order_by(LocationServiceSetting.effective_from.desc())
        .limit(1)
    )
    if location_setting:
        facts.append(
            ConfigurationFact(
                fact_type="location_service_setting",
                value={
                    "online_enabled": location_setting.online_enabled,
                    "minimum_lead_minutes": location_setting.minimum_lead_minutes,
                    "booking_horizon_days": location_setting.booking_horizon_days,
                    "resource_type": location_setting.resource_type,
                    "resource_capacity": location_setting.resource_capacity,
                    "eligibility_rule": location_setting.eligibility_rule,
                },
                provenance=Provenance(
                    source_table="business.location_service_settings",
                    source_reference=str(location_setting.id),
                ),
            )
        )
    if attempt.requested_employee_id:
        employee_setting = await session.scalar(
            select(EmployeeBookingSetting)
            .where(
                EmployeeBookingSetting.employee_id == attempt.requested_employee_id,
                or_(
                    EmployeeBookingSetting.service_id == attempt.service_id,
                    EmployeeBookingSetting.service_id.is_(None),
                ),
                EmployeeBookingSetting.effective_from <= effective_date,
                or_(
                    EmployeeBookingSetting.effective_through.is_(None),
                    EmployeeBookingSetting.effective_through >= effective_date,
                ),
            )
            .order_by(
                EmployeeBookingSetting.service_id.is_(None),
                EmployeeBookingSetting.effective_from.desc(),
            )
            .limit(1)
        )
        if employee_setting:
            facts.append(
                ConfigurationFact(
                    fact_type="employee_booking_setting",
                    value={
                        "online_enabled": employee_setting.online_enabled,
                        "minimum_lead_minutes": employee_setting.minimum_lead_minutes,
                    },
                    provenance=Provenance(
                        source_table="business.employee_booking_settings",
                        source_reference=str(employee_setting.id),
                    ),
                )
            )

    service = await session.get(Service, attempt.service_id)
    assert service is not None
    requested_end = attempt.requested_start + timedelta(minutes=service.duration_minutes)

    hours = (
        (
            await session.execute(
                select(LocationBusinessHours).where(
                    LocationBusinessHours.location_id == attempt.location_id,
                    LocationBusinessHours.day_of_week == attempt.requested_start.weekday(),
                    LocationBusinessHours.valid_from <= effective_date,
                    or_(
                        LocationBusinessHours.valid_through.is_(None),
                        LocationBusinessHours.valid_through >= effective_date,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    facts.append(
        ConfigurationFact(
            fact_type="location_business_hours",
            condition="present" if hours else "known_absent",
            value={
                "intervals": [
                    {"opens_at": row.opens_at.isoformat(), "closes_at": row.closes_at.isoformat()}
                    for row in hours
                ]
            },
            provenance=Provenance(
                source_table="business.location_business_hours",
                source_reference=(
                    ",".join(str(row.id) for row in hours)
                    if hours
                    else f"query:{location_ref}:{effective_date.isoformat()}"
                ),
            ),
        )
    )
    location_offering = await session.scalar(
        select(LocationService).where(
            LocationService.location_id == attempt.location_id,
            LocationService.service_id == attempt.service_id,
            LocationService.valid_from <= effective_date,
            or_(
                LocationService.valid_through.is_(None),
                LocationService.valid_through >= effective_date,
            ),
        )
    )
    facts.append(
        ConfigurationFact(
            fact_type="location_service_offering",
            condition="present" if location_offering else "known_absent",
            value={"offered": location_offering.offered if location_offering else False},
            provenance=Provenance(
                source_table="business.location_services",
                source_reference=(
                    str(location_offering.id)
                    if location_offering
                    else f"query:{location_ref}:{service_ref}:{effective_date.isoformat()}"
                ),
            ),
        )
    )
    if attempt.requested_employee_id:
        employee_location = await session.scalar(
            select(EmployeeLocation).where(
                EmployeeLocation.employee_id == attempt.requested_employee_id,
                EmployeeLocation.location_id == attempt.location_id,
                EmployeeLocation.valid_from <= effective_date,
                or_(
                    EmployeeLocation.valid_through.is_(None),
                    EmployeeLocation.valid_through >= effective_date,
                ),
            )
        )
        facts.append(
            ConfigurationFact(
                fact_type="employee_location_assignment",
                condition="present" if employee_location else "known_absent",
                value={"assigned": employee_location is not None},
                provenance=Provenance(
                    source_table="business.employee_locations",
                    source_reference=(
                        str(employee_location.id)
                        if employee_location
                        else f"query:{employee_ref}:{location_ref}:{effective_date.isoformat()}"
                    ),
                ),
            )
        )
        qualification = await session.scalar(
            select(EmployeeService).where(
                EmployeeService.employee_id == attempt.requested_employee_id,
                EmployeeService.service_id == attempt.service_id,
                EmployeeService.valid_from <= effective_date,
                or_(
                    EmployeeService.valid_through.is_(None),
                    EmployeeService.valid_through >= effective_date,
                ),
            )
        )
        facts.append(
            ConfigurationFact(
                fact_type="employee_service_qualification",
                condition="present" if qualification else "known_absent",
                value={"qualified": qualification is not None},
                provenance=Provenance(
                    source_table="business.employee_services",
                    source_reference=(
                        str(qualification.id)
                        if qualification
                        else f"query:{employee_ref}:{service_ref}:{effective_date.isoformat()}"
                    ),
                ),
            )
        )
        schedules = (
            (
                await session.execute(
                    select(EmployeeSchedule).where(
                        EmployeeSchedule.employee_id == attempt.requested_employee_id,
                        EmployeeSchedule.location_id == attempt.location_id,
                        EmployeeSchedule.starts_at <= attempt.requested_start,
                        EmployeeSchedule.ends_at >= requested_end,
                    )
                )
            )
            .scalars()
            .all()
        )
        facts.append(
            ConfigurationFact(
                fact_type="employee_schedule_coverage",
                condition="present" if schedules else "known_absent",
                value={
                    "requested_end": requested_end.isoformat(),
                    "covering_intervals": [
                        {
                            "starts_at": row.starts_at.isoformat(),
                            "ends_at": row.ends_at.isoformat(),
                            "schedule_type": row.schedule_type,
                            "reason_code": row.reason_code,
                        }
                        for row in schedules
                    ],
                },
                provenance=Provenance(
                    source_table="business.employee_schedules",
                    source_reference=(
                        ",".join(str(row.id) for row in schedules)
                        if schedules
                        else f"query:{employee_ref}:{attempt.requested_start.isoformat()}"
                    ),
                ),
            )
        )

    blocks = (
        (
            await session.execute(
                select(BookingBlock).where(
                    BookingBlock.starts_at < requested_end,
                    BookingBlock.ends_at > attempt.requested_start,
                    or_(
                        BookingBlock.location_id.is_(None),
                        BookingBlock.location_id == attempt.location_id,
                    ),
                    or_(
                        BookingBlock.service_id.is_(None),
                        BookingBlock.service_id == attempt.service_id,
                    ),
                    or_(
                        BookingBlock.employee_id.is_(None),
                        BookingBlock.employee_id == attempt.requested_employee_id,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    facts.append(
        ConfigurationFact(
            fact_type="overlapping_booking_blocks",
            condition="present" if blocks else "known_absent",
            value={
                "blocks": [
                    {
                        "starts_at": row.starts_at.isoformat(),
                        "ends_at": row.ends_at.isoformat(),
                        "reason_code": row.reason_code,
                    }
                    for row in blocks
                ]
            },
            provenance=Provenance(
                source_table="business.booking_blocks",
                source_reference=(
                    ",".join(str(row.id) for row in blocks)
                    if blocks
                    else f"query:{location_ref}:{attempt.requested_start.isoformat()}"
                ),
            ),
        )
    )
    if service.required_resource_type:
        resources = (
            (
                await session.execute(
                    select(LocationResource).where(
                        LocationResource.location_id == attempt.location_id,
                        LocationResource.resource_type == service.required_resource_type,
                        LocationResource.active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        facts.append(
            ConfigurationFact(
                fact_type="location_resources",
                condition="present" if resources else "known_absent",
                value={
                    "required_resource_type": service.required_resource_type,
                    "resources": [
                        {"reference": row.public_reference, "capacity": row.capacity}
                        for row in resources
                    ],
                },
                provenance=Provenance(
                    source_table="business.location_resources",
                    source_reference=(
                        ",".join(row.public_reference for row in resources)
                        if resources
                        else f"query:{location_ref}:{service.required_resource_type}"
                    ),
                ),
            )
        )

    conflicts = (
        (
            await session.execute(
                select(Appointment).where(
                    Appointment.employee_id == attempt.requested_employee_id,
                    Appointment.status.in_(["scheduled", "confirmed", "checked_in"]),
                    Appointment.scheduled_start < requested_end,
                    Appointment.scheduled_end > attempt.requested_start,
                )
            )
        )
        .scalars()
        .all()
    )
    facts.append(
        ConfigurationFact(
            fact_type="overlapping_appointments",
            condition="present" if conflicts else "known_absent",
            value={
                "appointments": [row.public_reference for row in conflicts],
                "requested_end": requested_end.isoformat(),
            },
            provenance=Provenance(
                source_table="business.appointments",
                source_reference=(
                    ",".join(row.public_reference for row in conflicts)
                    if conflicts
                    else f"query:{employee_ref}:{attempt.requested_start.isoformat()}"
                ),
            ),
        )
    )

    data = BookingAttemptEvidence(
        booking_attempt_reference=attempt.public_reference,
        customer_reference=customer_ref,
        location_reference=location_ref,
        service_reference=service_ref,
        requested_employee_reference=employee_ref,
        requested_start=attempt.requested_start,
        status=attempt.status,
        reason_code=attempt.reason_code,
        committed_appointment_reference=appointment_ref,
        configuration_facts=facts,
        provenance=_provenance("booking_attempts", attempt.public_reference),
    )
    return ToolResult(metadata=_metadata("get_booking_attempt_evidence", 1 + len(facts)), data=data)
