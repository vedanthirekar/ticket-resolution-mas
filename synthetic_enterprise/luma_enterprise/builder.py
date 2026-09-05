from __future__ import annotations

import random
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from faker import Faker

from luma_enterprise.catalog import EMPLOYEES, LOCATIONS, SERVICES, ServiceSpec
from luma_enterprise.config import GenerationConfig
from luma_enterprise.identifiers import deterministic_id

Rows = dict[str, list[dict[str, Any]]]


def _row_id(config: GenerationConfig, entity: str, reference: str) -> UUID:
    return deterministic_id(config.dataset_version, entity, reference)


def _dated_rows(config: GenerationConfig, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    created = config.reference_time - timedelta(days=730)
    for row in rows:
        row.setdefault("created_at", created)
        row.setdefault("updated_at", created)
    return rows


def _date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _base_rows(config: GenerationConfig) -> tuple[Rows, dict[str, Any]]:
    generated_at = config.reference_time - timedelta(days=730)
    rows: Rows = {}

    rows["locations"] = _dated_rows(
        config,
        [
            {
                "id": _row_id(config, "location", spec.reference),
                "public_reference": spec.reference,
                "name": spec.name,
                "timezone": spec.timezone,
                "currency": "USD",
                "active": True,
            }
            for spec in LOCATIONS
        ],
    )

    hours: list[dict[str, Any]] = []
    for location in LOCATIONS:
        for weekday, opens_hour, closes_hour in location.hours:
            reference = f"{location.reference}-{weekday}-2024"
            hours.append(
                {
                    "id": _row_id(config, "location_hours", reference),
                    "location_id": _row_id(config, "location", location.reference),
                    "day_of_week": weekday,
                    "opens_at": time(opens_hour),
                    "closes_at": time(closes_hour),
                    "valid_from": date(2024, 1, 1),
                    "valid_through": None,
                }
            )
    rows["location_business_hours"] = hours

    rows["employees"] = _dated_rows(
        config,
        [
            {
                "id": _row_id(config, "employee", spec.reference),
                "public_reference": spec.reference,
                "display_name": spec.name,
                "role": spec.role,
                "home_location_id": _row_id(config, "location", spec.location_reference),
                "active": True,
            }
            for spec in EMPLOYEES
        ],
    )
    rows["employee_locations"] = [
        {
            "id": _row_id(config, "employee_location", spec.reference),
            "employee_id": _row_id(config, "employee", spec.reference),
            "location_id": _row_id(config, "location", spec.location_reference),
            "valid_from": date(2024, 1, 1),
            "valid_through": None,
        }
        for spec in EMPLOYEES
    ]

    rows["services"] = _dated_rows(
        config,
        [
            {
                "id": _row_id(config, "service", spec.reference),
                "public_reference": spec.reference,
                "name": spec.name,
                "category": spec.category,
                "duration_minutes": spec.duration_minutes,
                "base_price_cents": spec.price_cents,
                "currency": "USD",
                "credit_cost": spec.credit_cost,
                "qualification_code": spec.qualification,
                "required_resource_type": spec.resource_type,
                "is_add_on": spec.is_add_on,
                "active": True,
            }
            for spec in SERVICES
        ],
    )
    rows["location_services"] = [
        {
            "id": _row_id(config, "location_service", f"{location_ref}-{service.reference}-2024"),
            "location_id": _row_id(config, "location", location_ref),
            "service_id": _row_id(config, "service", service.reference),
            "offered": True,
            "price_override_cents": None,
            "valid_from": date(2024, 1, 1),
            "valid_through": None,
        }
        for service in SERVICES
        for location_ref in service.allowed_locations
    ]
    rows["employee_services"] = [
        {
            "id": _row_id(
                config, "employee_service", f"{employee.reference}-{service.reference}-2024"
            ),
            "employee_id": _row_id(config, "employee", employee.reference),
            "service_id": _row_id(config, "service", service.reference),
            "valid_from": date(2024, 1, 1),
            "valid_through": None,
        }
        for employee in EMPLOYEES
        for service in SERVICES
        if service.qualification in employee.qualifications
        and employee.location_reference in service.allowed_locations
    ]

    fake = Faker("en_US")
    fake.seed_instance(config.seed)
    customers: list[dict[str, Any]] = []
    for index in range(1, config.customer_count + 1):
        reference = f"CUS-{index:04d}"
        first_name = fake.first_name()
        last_name = fake.last_name()
        created_at = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=index % 600)
        customers.append(
            {
                "id": _row_id(config, "customer", reference),
                "public_reference": reference,
                "first_name": first_name,
                "last_name": last_name,
                "email": f"{first_name}.{last_name}.{index}@example.test".lower().replace("'", ""),
                "phone": f"+1317555{index:04d}",
                "email_verified": index % 7 != 0,
                "phone_verified": index % 5 != 0,
                "active": index % 29 != 0,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
    rows["customers"] = customers

    schedules: list[dict[str, Any]] = []
    location_by_ref = {location.reference: location for location in LOCATIONS}
    for employee in EMPLOYEES:
        location = location_by_ref[employee.location_reference]
        timezone = ZoneInfo(location.timezone)
        for work_date in _date_range(date(2025, 1, 1), date(2026, 12, 31)):
            if work_date.weekday() not in location.open_weekdays:
                continue
            business_hours = location.hours_for(work_date.weekday())
            if business_hours is None:
                continue
            opens_hour, closes_hour = business_hours
            if employee.reference == "EMP-002" and work_date == date(2026, 9, 12):
                continue
            local_start = datetime.combine(work_date, time(opens_hour), timezone)
            local_end = datetime.combine(work_date, time(closes_hour), timezone)
            reference = f"{employee.reference}-{work_date.isoformat()}"
            schedules.append(
                {
                    "id": _row_id(config, "employee_schedule", reference),
                    "employee_id": _row_id(config, "employee", employee.reference),
                    "location_id": _row_id(config, "location", location.reference),
                    "starts_at": local_start.astimezone(UTC),
                    "ends_at": local_end.astimezone(UTC),
                    "schedule_type": "available",
                    "reason_code": None,
                    "created_at": generated_at,
                    "updated_at": generated_at,
                }
            )
    rows["employee_schedules"] = schedules

    metadata = {
        "employee_by_ref": {employee.reference: employee for employee in EMPLOYEES},
        "service_by_ref": {service.reference: service for service in SERVICES},
        "location_by_ref": location_by_ref,
    }
    return rows, metadata


def _appointment_row(
    config: GenerationConfig,
    *,
    reference: str,
    customer_ref: str,
    location_ref: str,
    service: ServiceSpec,
    employee_ref: str,
    start: datetime,
    status: str,
    booking_channel: str,
    predecessor_ref: str | None = None,
    cancellation_time: datetime | None = None,
    cancellation_reason: str | None = None,
) -> dict[str, Any]:
    created_at = start - timedelta(days=14)
    return {
        "id": _row_id(config, "appointment", reference),
        "public_reference": reference,
        "customer_id": _row_id(config, "customer", customer_ref),
        "location_id": _row_id(config, "location", location_ref),
        "service_id": _row_id(config, "service", service.reference),
        "employee_id": _row_id(config, "employee", employee_ref),
        "predecessor_appointment_id": (
            _row_id(config, "appointment", predecessor_ref) if predecessor_ref else None
        ),
        "scheduled_start": start,
        "scheduled_end": start + timedelta(minutes=service.duration_minutes),
        "quoted_price_cents": service.price_cents,
        "quoted_credit_cost": service.credit_cost,
        "currency": "USD",
        "status": status,
        "booking_channel": booking_channel,
        "cancelled_at": cancellation_time,
        "current_cancellation_reason": cancellation_reason,
        "created_at": created_at,
        "updated_at": max(created_at, cancellation_time or created_at),
    }


def _event_row(
    config: GenerationConfig,
    *,
    appointment_ref: str,
    sequence: int,
    event_type: str,
    occurred_at: datetime,
    actor_type: str,
    actor_reference: str,
    initiating_party: str = "not_applicable",
    reason_code: str | None = None,
    channel: str = "internal",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reference = f"AEVT-{appointment_ref.removeprefix('APPT-')}-{sequence:02d}"
    return {
        "id": _row_id(config, "appointment_event", reference),
        "public_reference": reference,
        "appointment_id": _row_id(config, "appointment", appointment_ref),
        "event_type": event_type,
        "actor_type": actor_type,
        "actor_reference": actor_reference,
        "initiating_party": initiating_party,
        "reason_code": reason_code,
        "occurred_at": occurred_at,
        "recorded_at": occurred_at + timedelta(minutes=1),
        "channel": channel,
        "correlation_reference": f"CORR-{appointment_ref}",
        "external_reference": None,
        "causation_event_id": None,
        "metadata": metadata or {},
        "created_at": occurred_at + timedelta(minutes=1),
    }


def _build_background_appointments(
    config: GenerationConfig,
    *,
    rng: random.Random,
    count: int,
    metadata: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    providers = [employee for employee in EMPLOYEES if employee.qualifications]
    services_by_provider: dict[str, list[ServiceSpec]] = {
        employee.reference: [
            service
            for service in SERVICES
            if not service.is_add_on
            and service.qualification in employee.qualifications
            and employee.location_reference in service.allowed_locations
        ]
        for employee in providers
    }
    location_by_ref = metadata["location_by_ref"]
    appointments: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    occupied: set[tuple[str, date, int]] = set()
    reserved_provider_days = {
        (spec["employee"], spec["local"].date()) for spec in _canonical_specs()
    }

    for index in range(1, count + 1):
        employee = providers[(index - 1) % len(providers)]
        location = location_by_ref[employee.location_reference]
        service = rng.choice(services_by_provider[employee.reference])

        while True:
            appointment_date = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 700))
            business_hours = location.hours_for(appointment_date.weekday())
            if business_hours is None:
                continue
            opens_hour, closes_hour = business_hours
            slot_hour = rng.choice((opens_hour, opens_hour + 2, opens_hour + 4, opens_hour + 6))
            key = (employee.reference, appointment_date, slot_hour)
            if (
                key not in occupied
                and (employee.reference, appointment_date) not in reserved_provider_days
                and slot_hour * 60 + service.duration_minutes <= closes_hour * 60
            ):
                occupied.add(key)
                break

        start = datetime.combine(
            appointment_date, time(slot_hour), ZoneInfo(location.timezone)
        ).astimezone(UTC)
        reference = f"APPT-{index:06d}"
        customer_ref = f"CUS-{rng.randint(1, config.customer_count):04d}"
        booking_channel = rng.choices(
            ("web", "mobile", "phone", "front_desk"), weights=(52, 18, 16, 14), k=1
        )[0]

        cancellation_time: datetime | None = None
        cancellation_reason: str | None = None
        initiating_party = "not_applicable"
        if start >= config.reference_time:
            status = "confirmed" if rng.random() < 0.45 else "scheduled"
        else:
            draw = rng.random()
            if draw < 0.78:
                status = "completed"
            elif draw < 0.94:
                status = "cancelled"
                initiating_party = rng.choices(
                    ("customer", "provider", "business"), weights=(76, 15, 9), k=1
                )[0]
                notice_hours = rng.choice((2, 6, 12, 30, 60))
                cancellation_time = start - timedelta(hours=notice_hours)
                cancellation_reason = {
                    "customer": "customer_request",
                    "provider": "provider_unavailable",
                    "business": "location_closed",
                }[initiating_party]
            else:
                status = "no_show"

        appointments.append(
            _appointment_row(
                config,
                reference=reference,
                customer_ref=customer_ref,
                location_ref=employee.location_reference,
                service=service,
                employee_ref=employee.reference,
                start=start,
                status=status,
                booking_channel=booking_channel,
                cancellation_time=cancellation_time,
                cancellation_reason=cancellation_reason,
            )
        )
        created_at = start - timedelta(days=rng.randint(2, 45))
        events.append(
            _event_row(
                config,
                appointment_ref=reference,
                sequence=1,
                event_type="appointment_created",
                occurred_at=created_at,
                actor_type="customer" if booking_channel in {"web", "mobile"} else "employee",
                actor_reference=(
                    customer_ref if booking_channel in {"web", "mobile"} else employee.reference
                ),
                channel=booking_channel,
            )
        )
        sequence = 2
        if status in {"confirmed", "completed", "no_show"}:
            events.append(
                _event_row(
                    config,
                    appointment_ref=reference,
                    sequence=sequence,
                    event_type="appointment_confirmed",
                    occurred_at=start - timedelta(hours=26),
                    actor_type="customer",
                    actor_reference=customer_ref,
                    channel="mobile",
                )
            )
            sequence += 1
        if status == "completed":
            events.extend(
                [
                    _event_row(
                        config,
                        appointment_ref=reference,
                        sequence=sequence,
                        event_type="customer_checked_in",
                        occurred_at=start - timedelta(minutes=5),
                        actor_type="employee",
                        actor_reference=employee.reference,
                        channel="front_desk",
                    ),
                    _event_row(
                        config,
                        appointment_ref=reference,
                        sequence=sequence + 1,
                        event_type="service_completed",
                        occurred_at=start + timedelta(minutes=service.duration_minutes),
                        actor_type="employee",
                        actor_reference=employee.reference,
                        channel="front_desk",
                    ),
                ]
            )
        elif status == "cancelled" and cancellation_time is not None:
            recorded_by_customer = initiating_party == "customer" and rng.random() < 0.45
            events.append(
                _event_row(
                    config,
                    appointment_ref=reference,
                    sequence=sequence,
                    event_type="appointment_cancelled",
                    occurred_at=cancellation_time,
                    actor_type="customer" if recorded_by_customer else "employee",
                    actor_reference=customer_ref if recorded_by_customer else employee.reference,
                    initiating_party=initiating_party,
                    reason_code=cancellation_reason,
                    channel="web" if recorded_by_customer else "phone",
                )
            )
        elif status == "no_show":
            events.append(
                _event_row(
                    config,
                    appointment_ref=reference,
                    sequence=sequence,
                    event_type="appointment_marked_no_show",
                    occurred_at=start + timedelta(minutes=15),
                    actor_type="employee",
                    actor_reference=employee.reference,
                    initiating_party="customer",
                    reason_code="customer_no_show",
                    channel="front_desk",
                )
            )

    return appointments, events


def _canonical_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "ref": "APPT-CAN-PROVIDER",
            "customer": "CUS-0001",
            "location": "LOC-IND",
            "service": "SVC-004",
            "employee": "EMP-002",
            "local": datetime(2026, 8, 20, 13, 0),
            "status": "cancelled",
        },
        {
            "ref": "APPT-CAN-FREE",
            "customer": "CUS-0003",
            "location": "LOC-CHI",
            "service": "SVC-001",
            "employee": "EMP-007",
            "local": datetime(2026, 7, 10, 12, 0),
            "status": "cancelled",
        },
        {
            "ref": "APPT-CAN-LATE",
            "customer": "CUS-0004",
            "location": "LOC-CHI",
            "service": "SVC-001",
            "employee": "EMP-007",
            "local": datetime(2026, 7, 11, 12, 0),
            "status": "cancelled",
        },
        {
            "ref": "APPT-NO-SHOW",
            "customer": "CUS-0005",
            "location": "LOC-DEN",
            "service": "SVC-001",
            "employee": "EMP-012",
            "local": datetime(2026, 7, 12, 12, 0),
            "status": "no_show",
        },
        {
            "ref": "APPT-AUTH-HOLD",
            "customer": "CUS-0006",
            "location": "LOC-IND",
            "service": "SVC-001",
            "employee": "EMP-002",
            "local": datetime(2026, 7, 13, 12, 0),
            "status": "cancelled",
        },
        {
            "ref": "APPT-DUP-PAY",
            "customer": "CUS-0007",
            "location": "LOC-IND",
            "service": "SVC-001",
            "employee": "EMP-005",
            "local": datetime(2026, 7, 14, 12, 0),
            "status": "completed",
        },
        {
            "ref": "APPT-DISTINCT-A",
            "customer": "CUS-0008",
            "location": "LOC-CHI",
            "service": "SVC-001",
            "employee": "EMP-007",
            "local": datetime(2026, 7, 15, 10, 0),
            "status": "completed",
        },
        {
            "ref": "APPT-DISTINCT-B",
            "customer": "CUS-0008",
            "location": "LOC-CHI",
            "service": "SVC-001",
            "employee": "EMP-007",
            "local": datetime(2026, 7, 16, 10, 0),
            "status": "completed",
        },
        {
            "ref": "APPT-MEM-DUP",
            "customer": "CUS-0001",
            "location": "LOC-IND",
            "service": "SVC-001",
            "employee": "EMP-005",
            "local": datetime(2026, 7, 21, 10, 0),
            "status": "completed",
        },
        {
            "ref": "APPT-MEM-CORRECT",
            "customer": "CUS-0002",
            "location": "LOC-CHI",
            "service": "SVC-001",
            "employee": "EMP-010",
            "local": datetime(2026, 7, 22, 10, 0),
            "status": "completed",
        },
        {
            "ref": "APPT-MISSING-EVENT",
            "customer": "CUS-0009",
            "location": "LOC-DEN",
            "service": "SVC-008",
            "employee": "EMP-013",
            "local": datetime(2026, 7, 23, 11, 0),
            "status": "cancelled",
        },
        {
            "ref": "APPT-CONFLICT",
            "customer": "CUS-0010",
            "location": "LOC-IND",
            "service": "SVC-001",
            "employee": "EMP-002",
            "local": datetime(2026, 7, 24, 11, 0),
            "status": "cancelled",
        },
        {
            "ref": "APPT-POLICY-V1",
            "customer": "CUS-0011",
            "location": "LOC-CHI",
            "service": "SVC-001",
            "employee": "EMP-007",
            "local": datetime(2025, 7, 2, 12, 0),
            "status": "cancelled",
        },
        {
            "ref": "APPT-POLICY-V2",
            "customer": "CUS-0012",
            "location": "LOC-CHI",
            "service": "SVC-001",
            "employee": "EMP-007",
            "local": datetime(2025, 7, 2, 14, 0),
            "status": "cancelled",
        },
        {
            "ref": "APPT-TRANSFER",
            "customer": "CUS-0013",
            "location": "LOC-IND",
            "service": "SVC-001",
            "employee": "EMP-002",
            "local": datetime(2026, 7, 25, 13, 0),
            "status": "completed",
        },
    )


def _build_canonical_appointments(
    config: GenerationConfig, metadata: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[str]]]:
    services = metadata["service_by_ref"]
    locations = metadata["location_by_ref"]
    appointments: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for spec in _canonical_specs():
        start = (
            spec["local"]
            .replace(tzinfo=ZoneInfo(locations[spec["location"]].timezone))
            .astimezone(UTC)
        )
        service = services[spec["service"]]
        cancellation_time: datetime | None = None
        cancellation_reason: str | None = None
        if spec["status"] == "cancelled":
            cancellation_time = start - timedelta(hours=4)
            cancellation_reason = "customer_request"
        if spec["ref"] == "APPT-CAN-PROVIDER":
            cancellation_time = start - timedelta(hours=2)
            cancellation_reason = "provider_unavailable"
        if spec["ref"] == "APPT-CAN-FREE":
            cancellation_time = start - timedelta(hours=30)
        if spec["ref"] == "APPT-POLICY-V1":
            cancellation_time = datetime(
                2025, 6, 30, 23, 59, tzinfo=ZoneInfo("America/Chicago")
            ).astimezone(UTC)
        if spec["ref"] == "APPT-POLICY-V2":
            cancellation_time = datetime(
                2025, 7, 1, 0, 0, tzinfo=ZoneInfo("America/Chicago")
            ).astimezone(UTC)

        appointments.append(
            _appointment_row(
                config,
                reference=spec["ref"],
                customer_ref=spec["customer"],
                location_ref=spec["location"],
                service=service,
                employee_ref=spec["employee"],
                start=start,
                status=spec["status"],
                booking_channel="web",
                cancellation_time=cancellation_time,
                cancellation_reason=cancellation_reason,
            )
        )
        events.append(
            _event_row(
                config,
                appointment_ref=spec["ref"],
                sequence=1,
                event_type="appointment_created",
                occurred_at=start - timedelta(days=10),
                actor_type="customer",
                actor_reference=spec["customer"],
                channel="web",
            )
        )

        if spec["ref"] == "APPT-MISSING-EVENT":
            continue
        if spec["ref"] == "APPT-TRANSFER":
            events.extend(
                [
                    _event_row(
                        config,
                        appointment_ref=spec["ref"],
                        sequence=2,
                        event_type="provider_unavailable",
                        occurred_at=start - timedelta(hours=3),
                        actor_type="employee",
                        actor_reference="EMP-005",
                        initiating_party="provider",
                        reason_code="provider_unavailable",
                        channel="phone",
                    ),
                    _event_row(
                        config,
                        appointment_ref=spec["ref"],
                        sequence=3,
                        event_type="provider_reassigned",
                        occurred_at=start - timedelta(hours=2, minutes=50),
                        actor_type="employee",
                        actor_reference="EMP-001",
                        initiating_party="business",
                        reason_code="accepted_transfer",
                        channel="phone",
                        metadata={
                            "customer_accepted": True,
                            "previous_provider": "EMP-005",
                            "replacement_provider": "EMP-002",
                        },
                    ),
                    _event_row(
                        config,
                        appointment_ref=spec["ref"],
                        sequence=4,
                        event_type="customer_checked_in",
                        occurred_at=start - timedelta(minutes=3),
                        actor_type="employee",
                        actor_reference="EMP-001",
                        channel="front_desk",
                    ),
                    _event_row(
                        config,
                        appointment_ref=spec["ref"],
                        sequence=5,
                        event_type="service_completed",
                        occurred_at=start + timedelta(minutes=service.duration_minutes),
                        actor_type="employee",
                        actor_reference="EMP-002",
                        channel="front_desk",
                    ),
                ]
            )
        elif spec["status"] == "completed":
            events.extend(
                [
                    _event_row(
                        config,
                        appointment_ref=spec["ref"],
                        sequence=2,
                        event_type="customer_checked_in",
                        occurred_at=start - timedelta(minutes=5),
                        actor_type="employee",
                        actor_reference=spec["employee"],
                        channel="front_desk",
                    ),
                    _event_row(
                        config,
                        appointment_ref=spec["ref"],
                        sequence=3,
                        event_type="service_completed",
                        occurred_at=start + timedelta(minutes=service.duration_minutes),
                        actor_type="employee",
                        actor_reference=spec["employee"],
                        channel="front_desk",
                    ),
                ]
            )
        elif spec["status"] == "no_show":
            events.append(
                _event_row(
                    config,
                    appointment_ref=spec["ref"],
                    sequence=2,
                    event_type="appointment_marked_no_show",
                    occurred_at=start + timedelta(minutes=15),
                    actor_type="employee",
                    actor_reference=spec["employee"],
                    initiating_party="customer",
                    reason_code="customer_no_show",
                    channel="front_desk",
                )
            )
        elif cancellation_time is not None:
            initiator = "provider" if spec["ref"] == "APPT-CAN-PROVIDER" else "customer"
            events.append(
                _event_row(
                    config,
                    appointment_ref=spec["ref"],
                    sequence=2,
                    event_type="appointment_cancelled",
                    occurred_at=cancellation_time,
                    actor_type="employee",
                    actor_reference=spec["employee"],
                    initiating_party=initiator,
                    reason_code=cancellation_reason,
                    channel="phone",
                )
            )
            if spec["ref"] == "APPT-CONFLICT":
                events.append(
                    _event_row(
                        config,
                        appointment_ref=spec["ref"],
                        sequence=3,
                        event_type="appointment_cancelled",
                        occurred_at=cancellation_time + timedelta(minutes=2),
                        actor_type="system",
                        actor_reference="legacy_import",
                        initiating_party="business",
                        reason_code="location_closed",
                        channel="batch",
                    )
                )

    incidents = {
        "provider_cancellation_incorrect_fee": ["APPT-CAN-PROVIDER"],
        "customer_cancellation_windows": ["APPT-CAN-FREE", "APPT-CAN-LATE"],
        "valid_no_show_fee": ["APPT-NO-SHOW"],
        "authorized_not_captured": ["APPT-AUTH-HOLD"],
        "duplicate_payment": ["APPT-DUP-PAY"],
        "legitimate_similar_payments": ["APPT-DISTINCT-A", "APPT-DISTINCT-B"],
        "duplicate_credit_consumption": ["APPT-MEM-DUP"],
        "correct_credit_consumption": ["APPT-MEM-CORRECT"],
        "missing_audit_evidence": ["APPT-MISSING-EVENT"],
        "conflicting_records": ["APPT-CONFLICT"],
        "policy_version_boundary": ["APPT-POLICY-V1", "APPT-POLICY-V2"],
        "accepted_provider_transfer": ["APPT-TRANSFER"],
    }
    return appointments, events, incidents


def _invoice_and_payment_rows(
    config: GenerationConfig,
    *,
    appointment: dict[str, Any],
    sequence: int,
    payment_status: str,
    amount_cents: int,
    item_type: str,
    suffix: str = "",
    obligation_reference: str | None = None,
) -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]
]:
    suffix_token = f"-{suffix}" if suffix else ""
    invoice_ref = f"INV-{sequence:06d}{suffix_token}"
    item_ref = f"ITEM-{sequence:06d}{suffix_token}"
    payment_ref = f"PAY-{sequence:06d}{suffix_token}"
    event_time = appointment["scheduled_end"]
    captured = (
        amount_cents if payment_status in {"captured", "partially_refunded", "refunded"} else 0
    )
    authorized = amount_cents if payment_status not in {"failed"} else 0
    refunded = 0
    if payment_status == "partially_refunded":
        refunded = max(1, amount_cents // 2)
    elif payment_status == "refunded":
        refunded = amount_cents
    invoice = {
        "id": _row_id(config, "invoice", invoice_ref),
        "public_reference": invoice_ref,
        "customer_id": appointment["customer_id"],
        "appointment_id": appointment["id"],
        "status": "paid" if captured else "open",
        "total_cents": amount_cents,
        "currency": "USD",
        "created_at": event_time,
        "updated_at": event_time,
    }
    item = {
        "id": _row_id(config, "invoice_item", item_ref),
        "public_reference": item_ref,
        "invoice_id": invoice["id"],
        "appointment_id": appointment["id"],
        "service_id": appointment["service_id"] if item_type == "primary_service" else None,
        "item_type": item_type,
        "description": item_type.replace("_", " ").title(),
        "quantity": 1,
        "amount_cents": amount_cents,
        "currency": "USD",
        "created_at": event_time,
    }
    payment = {
        "id": _row_id(config, "payment", payment_ref),
        "public_reference": payment_ref,
        "invoice_id": invoice["id"],
        "customer_id": appointment["customer_id"],
        "obligation_reference": obligation_reference or invoice_ref,
        "status": payment_status,
        "tender_type": "card",
        "amount_cents": amount_cents,
        "authorized_amount_cents": authorized,
        "captured_amount_cents": captured,
        "refunded_amount_cents": refunded,
        "currency": "USD",
        "processor_reference": f"proc_{payment_ref.lower()}",
        "idempotency_key": f"idem_{payment_ref.lower()}",
        "created_at": event_time,
        "updated_at": event_time + timedelta(minutes=2),
    }
    authorization_event_ref = f"PEVT-{sequence:06d}{suffix_token}-A"
    payment_events = [
        {
            "id": _row_id(config, "payment_event", authorization_event_ref),
            "public_reference": authorization_event_ref,
            "payment_id": payment["id"],
            "event_type": "payment_failed" if payment_status == "failed" else "payment_authorized",
            "amount_cents": authorized,
            "actor_type": "external_provider",
            "actor_reference": "mock_processor",
            "occurred_at": event_time,
            "recorded_at": event_time + timedelta(seconds=2),
            "processor_event_reference": f"evt_{payment_ref.lower()}_auth",
            "correlation_reference": f"CORR-{payment_ref}",
            "metadata": {},
            "created_at": event_time + timedelta(seconds=2),
        }
    ]
    if captured:
        capture_event_ref = f"PEVT-{sequence:06d}{suffix_token}-C"
        payment_events.append(
            {
                "id": _row_id(config, "payment_event", capture_event_ref),
                "public_reference": capture_event_ref,
                "payment_id": payment["id"],
                "event_type": "payment_captured",
                "amount_cents": captured,
                "actor_type": "external_provider",
                "actor_reference": "mock_processor",
                "occurred_at": event_time + timedelta(seconds=5),
                "recorded_at": event_time + timedelta(seconds=7),
                "processor_event_reference": f"evt_{payment_ref.lower()}_capture",
                "correlation_reference": f"CORR-{payment_ref}",
                "metadata": {},
                "created_at": event_time + timedelta(seconds=7),
            }
        )
    refunds: list[dict[str, Any]] = []
    if refunded:
        refund_ref = f"REF-{sequence:06d}{suffix_token}"
        refund_time = event_time + timedelta(days=2)
        refunds.append(
            {
                "id": _row_id(config, "refund", refund_ref),
                "public_reference": refund_ref,
                "payment_id": payment["id"],
                "amount_cents": refunded,
                "status": "succeeded",
                "reason_code": "customer_refund",
                "processor_reference": f"proc_{refund_ref.lower()}",
                "idempotency_key": f"idem_{refund_ref.lower()}",
                "completed_at": refund_time,
                "created_at": refund_time,
                "updated_at": refund_time,
            }
        )
    return invoice, item, payment, payment_events, refunds


def _build_billing(
    config: GenerationConfig,
    *,
    rng: random.Random,
    appointments: list[dict[str, Any]],
) -> tuple[Rows, dict[str, list[str]]]:
    rows: Rows = {
        "invoices": [],
        "invoice_items": [],
        "payments": [],
        "payment_events": [],
        "refunds": [],
    }
    background = [
        appointment
        for appointment in appointments
        if appointment["public_reference"].startswith("APPT-0")
    ]
    candidates = [
        appointment
        for appointment in background
        if appointment["status"] in {"completed", "no_show"}
    ]
    for sequence, appointment in enumerate(candidates[: config.background_payment_count], start=1):
        if appointment["status"] == "no_show":
            item_type = "no_show_fee"
            amount = min(appointment["quoted_price_cents"], 15000)
        else:
            item_type = "primary_service"
            amount = appointment["quoted_price_cents"]
        draw = rng.random()
        status = (
            "captured"
            if draw < 0.88
            else "authorized"
            if draw < 0.92
            else "failed"
            if draw < 0.95
            else "voided"
            if draw < 0.97
            else "partially_refunded"
            if draw < 0.985
            else "refunded"
        )
        invoice, item, payment, events, refunds = _invoice_and_payment_rows(
            config,
            appointment=appointment,
            sequence=sequence,
            payment_status=status,
            amount_cents=amount,
            item_type=item_type,
        )
        rows["invoices"].append(invoice)
        rows["invoice_items"].append(item)
        rows["payments"].append(payment)
        rows["payment_events"].extend(events)
        rows["refunds"].extend(refunds)

    by_ref = {appointment["public_reference"]: appointment for appointment in appointments}
    canonical = (
        ("APPT-CAN-PROVIDER", "captured", 8000, "cancellation_fee", "provider-fee"),
        ("APPT-CAN-LATE", "captured", 6000, "cancellation_fee", "late-fee"),
        ("APPT-NO-SHOW", "captured", 12000, "no_show_fee", "no-show"),
        ("APPT-AUTH-HOLD", "authorized", 6000, "cancellation_fee", "auth-hold"),
        ("APPT-DUP-PAY", "captured", 12000, "primary_service", "duplicate-a"),
        ("APPT-DISTINCT-A", "captured", 12000, "primary_service", "distinct-a"),
        ("APPT-DISTINCT-B", "captured", 12000, "primary_service", "distinct-b"),
        ("APPT-POLICY-V1", "captured", 6000, "cancellation_fee", "policy-v1"),
        ("APPT-POLICY-V2", "captured", 6000, "cancellation_fee", "policy-v2"),
    )
    canonical_payment_refs: dict[str, list[str]] = {}
    base_sequence = config.background_payment_count + 1
    duplicate_obligation: str | None = None
    duplicate_invoice_id = None
    for offset, (appointment_ref, status, amount, item_type, suffix) in enumerate(canonical):
        appointment = by_ref[appointment_ref]
        invoice, item, payment, events, refunds = _invoice_and_payment_rows(
            config,
            appointment=appointment,
            sequence=base_sequence + offset,
            payment_status=status,
            amount_cents=amount,
            item_type=item_type,
            suffix=suffix,
        )
        if appointment_ref == "APPT-DUP-PAY":
            duplicate_obligation = invoice["public_reference"]
            duplicate_invoice_id = invoice["id"]
        rows["invoices"].append(invoice)
        rows["invoice_items"].append(item)
        rows["payments"].append(payment)
        rows["payment_events"].extend(events)
        rows["refunds"].extend(refunds)
        canonical_payment_refs.setdefault(appointment_ref, []).append(payment["public_reference"])

    duplicate_appointment = by_ref["APPT-DUP-PAY"]
    sequence = base_sequence + len(canonical)
    invoice, item, payment, events, refunds = _invoice_and_payment_rows(
        config,
        appointment=duplicate_appointment,
        sequence=sequence,
        payment_status="captured",
        amount_cents=12000,
        item_type="primary_service",
        suffix="duplicate-b",
        obligation_reference=duplicate_obligation,
    )
    # The second processor attempt settles the first invoice/obligation; its generated
    # invoice and item are discarded so the duplicate is not given a second consideration.
    payment["invoice_id"] = duplicate_invoice_id
    rows["payments"].append(payment)
    rows["payment_events"].extend(events)
    canonical_payment_refs["APPT-DUP-PAY"].append(payment["public_reference"])
    return rows, canonical_payment_refs


def _build_memberships(
    config: GenerationConfig,
    *,
    appointments: list[dict[str, Any]],
) -> Rows:
    rows: Rows = {
        "membership_plans": [],
        "memberships": [],
        "membership_ledger": [],
        "membership_credit_allocations": [],
    }
    plan_specs = (
        ("PLAN-ESSENTIAL", "Essential", 10900, 1, 3),
        ("PLAN-PLUS", "Plus", 19900, 2, 6),
        ("PLAN-PREMIER", "Premier", 36900, 4, 12),
    )
    for reference, name, price, plan_grant, ceiling in plan_specs:
        rows["membership_plans"].append(
            {
                "id": _row_id(config, "membership_plan", reference),
                "public_reference": reference,
                "name": name,
                "monthly_price_cents": price,
                "monthly_credit_grant": plan_grant,
                "rollover_ceiling": ceiling,
                "currency": "USD",
                "effective_from": date(2026, 1, 1),
                "effective_through": None,
                "created_at": datetime(2025, 10, 1, tzinfo=UTC),
                "updated_at": datetime(2025, 10, 1, tzinfo=UTC),
            }
        )

    grants_by_customer: dict[str, list[dict[str, Any]]] = {}
    membership_id_by_customer: dict[str, Any] = {}
    for index in range(1, config.membership_count + 1):
        customer_ref = f"CUS-{index:04d}"
        membership_ref = f"MEM-{index:04d}"
        plan_ref, _, _, grant_quantity, _ = plan_specs[(index - 1) % len(plan_specs)]
        status = (
            "active"
            if index % 10 < 7
            else "paused"
            if index % 10 == 7
            else "cancelled"
            if index % 10 == 8
            else "expired"
        )
        membership_id = _row_id(config, "membership", membership_ref)
        membership_id_by_customer[customer_ref] = membership_id
        rows["memberships"].append(
            {
                "id": membership_id,
                "public_reference": membership_ref,
                "customer_id": _row_id(config, "customer", customer_ref),
                "plan_id": _row_id(config, "membership_plan", plan_ref),
                "status": status,
                "starts_at": date(2025, 1, 1) + timedelta(days=index % 180),
                "ends_at": date(2026, 8, 1) if status in {"cancelled", "expired"} else None,
                "next_renewal_at": config.reference_time + timedelta(days=index % 28)
                if status == "active"
                else None,
                "terms_policy_id": "POL-MEM",
                "terms_version": 2,
                "created_at": datetime(2025, 1, 1, tzinfo=UTC),
                "updated_at": config.reference_time - timedelta(days=1),
            }
        )
        grants_by_customer[customer_ref] = []
        for grant_index, days_ago in enumerate((75, 45, 15), start=1):
            grant_ref = f"LEDGER-{index:04d}-GRANT-{grant_index}"
            effective_at = config.reference_time - timedelta(days=days_ago)
            grant_row = {
                "id": _row_id(config, "membership_ledger", grant_ref),
                "public_reference": grant_ref,
                "membership_id": membership_id,
                "entry_type": "grant",
                "credit_delta": grant_quantity,
                "effective_at": effective_at,
                "recorded_at": effective_at,
                "expires_at": effective_at + timedelta(days=90),
                "related_appointment_id": None,
                "related_entry_id": None,
                "actor_type": "system",
                "actor_reference": "membership_billing",
                "reason_code": "monthly_grant",
                "approval_reference": None,
                "idempotency_key": f"idem_{grant_ref.lower()}",
                "created_at": effective_at,
                "remaining": grant_quantity,
            }
            grants_by_customer[customer_ref].append(grant_row)
            rows["membership_ledger"].append(grant_row)
        if index % 5 == 0:
            expired_grant_ref = f"LEDGER-{index:04d}-GRANT-EXPIRED"
            expired_at = config.reference_time - timedelta(days=30)
            expired_grant = {
                "id": _row_id(config, "membership_ledger", expired_grant_ref),
                "public_reference": expired_grant_ref,
                "membership_id": membership_id,
                "entry_type": "grant",
                "credit_delta": grant_quantity,
                "effective_at": expired_at - timedelta(days=90),
                "recorded_at": expired_at - timedelta(days=90),
                "expires_at": expired_at,
                "related_appointment_id": None,
                "related_entry_id": None,
                "actor_type": "system",
                "actor_reference": "membership_billing",
                "reason_code": "monthly_grant",
                "approval_reference": None,
                "idempotency_key": f"idem_{expired_grant_ref.lower()}",
                "created_at": expired_at - timedelta(days=90),
                "remaining": 0,
            }
            expiration_ref = f"LEDGER-{index:04d}-EXPIRE"
            expiration = {
                "id": _row_id(config, "membership_ledger", expiration_ref),
                "public_reference": expiration_ref,
                "membership_id": membership_id,
                "entry_type": "expire",
                "credit_delta": -grant_quantity,
                "effective_at": expired_at,
                "recorded_at": expired_at,
                "expires_at": None,
                "related_appointment_id": None,
                "related_entry_id": expired_grant["id"],
                "actor_type": "system",
                "actor_reference": "membership_expiration",
                "reason_code": "grant_expired",
                "approval_reference": None,
                "idempotency_key": f"idem_{expiration_ref.lower()}",
                "created_at": expired_at,
            }
            grants_by_customer[customer_ref].append(expired_grant)
            rows["membership_ledger"].extend([expired_grant, expiration])

    appointments_by_ref = {row["public_reference"]: row for row in appointments}
    customer_ref_by_id = {
        _row_id(config, "customer", f"CUS-{index:04d}"): f"CUS-{index:04d}"
        for index in range(1, config.membership_count + 1)
    }
    credit_eligible_service_ids = {
        _row_id(config, "service", service.reference)
        for service in SERVICES
        if service.credit_cost is not None and not service.is_add_on
    }
    selected: list[tuple[str, dict[str, Any]]] = []
    used_customers: set[str] = {"CUS-0001", "CUS-0002"}
    for appointment in appointments:
        candidate_customer_ref = customer_ref_by_id.get(appointment["customer_id"])
        if (
            candidate_customer_ref is not None
            and appointment["status"] == "completed"
            and appointment["service_id"] in credit_eligible_service_ids
            and config.reference_time - timedelta(days=75)
            <= appointment["scheduled_end"]
            <= config.reference_time
            and candidate_customer_ref not in used_customers
        ):
            selected.append((candidate_customer_ref, appointment))
            used_customers.add(candidate_customer_ref)
        if len(selected) >= 80:
            break

    canonical_consumptions = (
        ("CUS-0001", appointments_by_ref["APPT-MEM-DUP"], 2),
        ("CUS-0002", appointments_by_ref["APPT-MEM-CORRECT"], 1),
    )
    consumption_number = 1
    for customer_ref, appointment, repetitions in (
        *canonical_consumptions,
        *((customer, appointment, 1) for customer, appointment in selected),
    ):
        if customer_ref not in membership_id_by_customer:
            continue
        for _ in range(repetitions):
            available_grant = next(
                (grant for grant in grants_by_customer[customer_ref] if grant["remaining"] > 0),
                None,
            )
            if available_grant is None:
                break
            ledger_ref = f"LEDGER-CONSUME-{consumption_number:05d}"
            consumption_id = _row_id(config, "membership_ledger", ledger_ref)
            rows["membership_ledger"].append(
                {
                    "id": consumption_id,
                    "public_reference": ledger_ref,
                    "membership_id": membership_id_by_customer[customer_ref],
                    "entry_type": "consume",
                    "credit_delta": -1,
                    "effective_at": appointment["scheduled_end"],
                    "recorded_at": appointment["scheduled_end"],
                    "expires_at": None,
                    "related_appointment_id": appointment["id"],
                    "related_entry_id": None,
                    "actor_type": "system",
                    "actor_reference": "appointment_settlement",
                    "reason_code": "service_completed",
                    "approval_reference": None,
                    "idempotency_key": f"idem_{ledger_ref.lower()}",
                    "created_at": appointment["scheduled_end"],
                }
            )
            allocation_ref = f"ALLOC-{consumption_number:05d}"
            rows["membership_credit_allocations"].append(
                {
                    "id": _row_id(config, "membership_allocation", allocation_ref),
                    "consumption_entry_id": consumption_id,
                    "grant_entry_id": available_grant["id"],
                    "quantity": 1,
                    "created_at": appointment["scheduled_end"],
                }
            )
            available_grant["remaining"] -= 1
            consumption_number += 1

    for ledger_entry in rows["membership_ledger"]:
        ledger_entry.pop("remaining", None)
    return rows


def _build_booking(
    config: GenerationConfig,
    *,
    appointments: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> tuple[Rows, dict[str, list[str]]]:
    rows: Rows = {
        "booking_settings": [],
        "location_service_settings": [],
        "employee_booking_settings": [],
        "location_resources": [],
        "booking_blocks": [],
        "booking_attempts": [],
    }
    created_at = datetime(2024, 1, 1, tzinfo=UTC)
    rows["booking_settings"].append(
        {
            "id": _row_id(config, "booking_setting", "COMPANY-2024"),
            "minimum_lead_minutes": 120,
            "booking_horizon_days": 60,
            "effective_from": date(2024, 1, 1),
            "effective_through": None,
            "created_at": created_at,
            "updated_at": created_at,
        }
    )
    for service in SERVICES:
        for location_ref in service.allowed_locations:
            reference = f"{location_ref}-{service.reference}-2024"
            rows["location_service_settings"].append(
                {
                    "id": _row_id(config, "location_service_setting", reference),
                    "location_id": _row_id(config, "location", location_ref),
                    "service_id": _row_id(config, "service", service.reference),
                    "online_enabled": not service.is_add_on,
                    "minimum_lead_minutes": 1440 if service.reference == "SVC-013" else None,
                    "booking_horizon_days": None,
                    "resource_type": service.resource_type,
                    "resource_capacity": (
                        1
                        if service.resource_type == "facial_room"
                        else 3
                        if location_ref == "LOC-DEN" and service.resource_type
                        else 2
                        if service.resource_type
                        else None
                    ),
                    "eligibility_rule": (
                        {"minimum_age": 18} if service.reference == "SVC-013" else {}
                    ),
                    "effective_from": date(2024, 1, 1),
                    "effective_through": None,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

    employee_setting_specs = (
        ("EMP-002", "SVC-003", False, None, "CANONICAL-DISABLED"),
        ("EMP-014", None, True, 240, "DEN-LEAD-OVERRIDE"),
        ("EMP-008", "SVC-013", True, 2880, "PEEL-LEAD-OVERRIDE"),
    )
    for employee_ref, service_ref, enabled, lead, reference in employee_setting_specs:
        rows["employee_booking_settings"].append(
            {
                "id": _row_id(config, "employee_booking_setting", reference),
                "employee_id": _row_id(config, "employee", employee_ref),
                "service_id": (
                    _row_id(config, "service", service_ref) if service_ref is not None else None
                ),
                "online_enabled": enabled,
                "minimum_lead_minutes": lead,
                "effective_from": date(2026, 1, 1),
                "effective_through": None,
                "created_at": datetime(2025, 12, 1, tzinfo=UTC),
                "updated_at": datetime(2025, 12, 1, tzinfo=UTC),
            }
        )

    for location in LOCATIONS:
        for resource_type, capacity in (
            ("facial_room", 1),
            ("recovery_station", 3 if location.reference == "LOC-DEN" else 2),
        ):
            reference = f"RES-{location.reference.removeprefix('LOC-')}-{resource_type.upper()}"
            rows["location_resources"].append(
                {
                    "id": _row_id(config, "location_resource", reference),
                    "public_reference": reference,
                    "location_id": _row_id(config, "location", location.reference),
                    "resource_type": resource_type,
                    "name": resource_type.replace("_", " ").title(),
                    "capacity": capacity,
                    "active": True,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

    for index in range(1, 46):
        employee = EMPLOYEES[index % len(EMPLOYEES)]
        starts_at = config.reference_time + timedelta(days=index, hours=index % 5)
        rows["booking_blocks"].append(
            {
                "id": _row_id(config, "booking_block", f"BLOCK-{index:03d}"),
                "location_id": None,
                "employee_id": _row_id(config, "employee", employee.reference),
                "service_id": None,
                "resource_id": None,
                "starts_at": starts_at,
                "ends_at": starts_at + timedelta(hours=2),
                "reason_code": "provider_time_off",
                "created_at": config.reference_time - timedelta(days=10),
                "updated_at": config.reference_time - timedelta(days=10),
            }
        )

    web_appointments = [
        appointment for appointment in appointments if appointment["booking_channel"] == "web"
    ]
    for index in range(1, 201):
        committed = index <= 120
        failed = index > 190
        appointment = web_appointments[index - 1] if committed else web_appointments[index]
        reference = f"BATT-{index:05d}"
        rows["booking_attempts"].append(
            {
                "id": _row_id(config, "booking_attempt", reference),
                "public_reference": reference,
                "idempotency_key": f"idem_{reference.lower()}",
                "correlation_reference": f"CORR-{reference}",
                "customer_id": appointment["customer_id"],
                "location_id": appointment["location_id"],
                "service_id": appointment["service_id"],
                "requested_employee_id": appointment["employee_id"],
                "requested_start": appointment["scheduled_start"],
                "channel": "web",
                "status": "committed" if committed else "failed" if failed else "rejected",
                "reason_code": (
                    None
                    if committed
                    else "technical_failure"
                    if failed
                    else "slot_no_longer_available"
                ),
                "appointment_id": appointment["id"] if committed else None,
                "created_at": appointment["created_at"],
                "updated_at": appointment["created_at"] + timedelta(seconds=2),
            }
        )

    canonical_attempts = (
        (
            "BATT-PROVIDER-OVERRIDE",
            "CUS-0020",
            "LOC-IND",
            "SVC-003",
            "EMP-002",
            datetime(2026, 9, 10, 12, 0),
            "employee_online_disabled",
        ),
        (
            "BATT-NO-QUALIFICATION",
            "CUS-0021",
            "LOC-IND",
            "SVC-013",
            "EMP-005",
            datetime(2026, 9, 10, 14, 0),
            "provider_not_qualified",
        ),
        (
            "BATT-OUTSIDE-SCHEDULE",
            "CUS-0022",
            "LOC-IND",
            "SVC-001",
            "EMP-002",
            datetime(2026, 9, 12, 12, 0),
            "outside_provider_schedule",
        ),
        (
            "BATT-LOCATION-CLOSED",
            "CUS-0023",
            "LOC-DEN",
            "SVC-001",
            "EMP-012",
            datetime(2026, 9, 14, 12, 0),
            "location_closed",
        ),
        (
            "BATT-TECHNICAL-FAILURE",
            "CUS-0024",
            "LOC-IND",
            "SVC-001",
            "EMP-002",
            datetime(2026, 9, 15, 12, 0),
            "technical_failure",
        ),
    )
    location_by_ref = metadata["location_by_ref"]
    for (
        reference,
        customer_ref,
        location_ref,
        service_ref,
        employee_ref,
        local_time,
        reason,
    ) in canonical_attempts:
        requested_start = local_time.replace(
            tzinfo=ZoneInfo(location_by_ref[location_ref].timezone)
        ).astimezone(UTC)
        rows["booking_attempts"].append(
            {
                "id": _row_id(config, "booking_attempt", reference),
                "public_reference": reference,
                "idempotency_key": f"idem_{reference.lower()}",
                "correlation_reference": f"CORR-{reference}",
                "customer_id": _row_id(config, "customer", customer_ref),
                "location_id": _row_id(config, "location", location_ref),
                "service_id": _row_id(config, "service", service_ref),
                "requested_employee_id": _row_id(config, "employee", employee_ref),
                "requested_start": requested_start,
                "channel": "web",
                "status": "failed" if reason == "technical_failure" else "rejected",
                "reason_code": reason,
                "appointment_id": None,
                "created_at": config.reference_time,
                "updated_at": config.reference_time + timedelta(seconds=2),
            }
        )

    incident_refs = {
        "employee_override": ["BATT-PROVIDER-OVERRIDE"],
        "qualification_unavailable": ["BATT-NO-QUALIFICATION"],
        "schedule_unavailable": ["BATT-OUTSIDE-SCHEDULE"],
        "location_unavailable": ["BATT-LOCATION-CLOSED"],
        "technical_booking_failure": ["BATT-TECHNICAL-FAILURE"],
    }
    return rows, incident_refs


def _build_audit(config: GenerationConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(1, 121):
        reference = f"AUD-{index:05d}"
        occurred_at = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index * 3)
        target = SERVICES[index % len(SERVICES)].reference
        rows.append(
            {
                "id": _row_id(config, "audit_event", reference),
                "public_reference": reference,
                "target_type": "location_service_setting",
                "target_reference": target,
                "action": "configuration_reviewed",
                "actor_type": "employee",
                "actor_reference": EMPLOYEES[index % len(EMPLOYEES)].reference,
                "occurred_at": occurred_at,
                "recorded_at": occurred_at,
                "correlation_reference": f"CORR-{reference}",
                "metadata": {"review_cycle": "quarterly"},
            }
        )
    return rows


def build_operational_rows(config: GenerationConfig) -> tuple[Rows, dict[str, list[str]]]:
    rng = random.Random(config.seed)
    rows, metadata = _base_rows(config)
    canonical_specs = _canonical_specs()
    background_count = config.appointment_count - len(canonical_specs)
    background_appointments, background_events = _build_background_appointments(
        config, rng=rng, count=background_count, metadata=metadata
    )
    canonical_appointments, canonical_events, incidents = _build_canonical_appointments(
        config, metadata
    )
    appointments = background_appointments + canonical_appointments
    rows["appointments"] = appointments
    rows["appointment_events"] = background_events + canonical_events

    billing_rows, payment_incidents = _build_billing(config, rng=rng, appointments=appointments)
    rows.update(billing_rows)
    incidents.update(
        {
            "duplicate_payment_records": payment_incidents["APPT-DUP-PAY"],
            "authorization_hold_record": payment_incidents["APPT-AUTH-HOLD"],
        }
    )
    rows.update(_build_memberships(config, appointments=appointments))
    booking_rows, booking_incidents = _build_booking(
        config, appointments=appointments, metadata=metadata
    )
    rows.update(booking_rows)
    incidents.update(booking_incidents)
    rows["audit_events"] = _build_audit(config)
    return rows, incidents
