from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.base import Base
from luma.db.models import (
    Appointment,
    AppointmentEvent,
    Customer,
    Employee,
    EmployeeLocation,
    EmployeeService,
    Invoice,
    InvoiceItem,
    Location,
    LocationService,
    Membership,
    MembershipCreditAllocation,
    MembershipLedgerEntry,
    MembershipPlan,
    Payment,
    PolicyDocument,
    PolicySection,
    PolicyVersion,
    Service,
)
from luma.services.refunds import RefundValidationError, create_pending_refund

pytestmark = pytest.mark.integration


async def test_database_contains_every_declared_business_and_knowledge_table(database) -> None:
    async with database.engine.connect() as connection:
        actual = await connection.run_sync(
            lambda sync_connection: {
                (schema, table)
                for schema in ("business", "knowledge")
                for table in inspect(sync_connection).get_table_names(schema=schema)
            }
        )

    expected = {
        (table.schema, table.name)
        for table in Base.metadata.sorted_tables
        if table.schema in {"business", "knowledge"}
    }
    assert actual == expected


async def test_migration_schema_matches_sqlalchemy_metadata(database) -> None:
    def schema_differences(sync_connection):
        context = MigrationContext.configure(
            sync_connection,
            opts={"include_schemas": True, "compare_type": True},
        )
        return [
            difference
            for difference in compare_metadata(context, Base.metadata)
            if not (
                (
                    difference[0] == "remove_table"
                    and difference[1].schema is None
                    and (
                        difference[1].name == "alembic_version"
                        or difference[1].name.startswith("checkpoint")
                    )
                )
                or (
                    difference[0] == "remove_index"
                    and difference[1].table.schema is None
                    and difference[1].table.name.startswith("checkpoint")
                )
            )
        ]

    async with database.engine.connect() as connection:
        differences = await connection.run_sync(schema_differences)

    assert differences == []


async def test_connected_operational_and_policy_records_can_be_inserted(database) -> None:
    now = datetime(2026, 6, 15, 15, 0, tzinfo=UTC)

    async with database.engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            location = Location(
                public_reference="LOC-TEST",
                name="Test Studio",
                timezone="America/Indiana/Indianapolis",
                currency="USD",
                active=True,
            )
            customer = Customer(
                public_reference="CUS-TEST",
                first_name="Test",
                last_name="Customer",
                email="schema-test@example.test",
                email_verified=True,
                phone_verified=False,
                active=True,
            )
            session.add_all([location, customer])
            await session.flush()

            employee = Employee(
                public_reference="EMP-TEST",
                display_name="Test Provider",
                role="massage_therapist",
                home_location_id=location.id,
                active=True,
            )
            service = Service(
                public_reference="SVC-TEST",
                name="Schema Test Service",
                category="massage",
                duration_minutes=50,
                base_price_cents=12000,
                currency="USD",
                credit_cost=1,
                qualification_code="massage-core",
                is_add_on=False,
                active=True,
            )
            session.add_all([employee, service])
            await session.flush()
            session.add_all(
                [
                    EmployeeLocation(
                        employee_id=employee.id,
                        location_id=location.id,
                        valid_from=date(2024, 1, 1),
                    ),
                    EmployeeService(
                        employee_id=employee.id,
                        service_id=service.id,
                        valid_from=date(2024, 1, 1),
                    ),
                    LocationService(
                        location_id=location.id,
                        service_id=service.id,
                        offered=True,
                        valid_from=date(2024, 1, 1),
                    ),
                ]
            )
            await session.flush()

            appointment = Appointment(
                public_reference="APPT-TEST",
                customer_id=customer.id,
                location_id=location.id,
                service_id=service.id,
                employee_id=employee.id,
                scheduled_start=now,
                scheduled_end=now + timedelta(minutes=50),
                quoted_price_cents=12000,
                quoted_credit_cost=1,
                currency="USD",
                status="completed",
                booking_channel="web",
            )
            session.add(appointment)
            await session.flush()
            session.add(
                AppointmentEvent(
                    public_reference="AEVT-TEST",
                    appointment_id=appointment.id,
                    event_type="service_completed",
                    actor_type="employee",
                    actor_reference=employee.public_reference,
                    initiating_party="not_applicable",
                    occurred_at=now + timedelta(minutes=50),
                    channel="front_desk",
                )
            )

            invoice = Invoice(
                public_reference="INV-TEST",
                customer_id=customer.id,
                appointment_id=appointment.id,
                status="paid",
                total_cents=12000,
                currency="USD",
            )
            session.add(invoice)
            await session.flush()
            session.add(
                InvoiceItem(
                    public_reference="ITEM-TEST",
                    invoice_id=invoice.id,
                    appointment_id=appointment.id,
                    service_id=service.id,
                    item_type="primary_service",
                    description="Schema Test Service",
                    quantity=1,
                    amount_cents=12000,
                    currency="USD",
                )
            )
            payment = Payment(
                public_reference="PAY-TEST",
                invoice_id=invoice.id,
                customer_id=customer.id,
                obligation_reference=invoice.public_reference,
                status="captured",
                tender_type="card",
                amount_cents=12000,
                authorized_amount_cents=12000,
                captured_amount_cents=12000,
                refunded_amount_cents=0,
                currency="USD",
                processor_reference="proc_test_capture",
                idempotency_key="pay_test_key",
            )
            session.add(payment)
            await session.flush()
            await create_pending_refund(
                session,
                payment_id=payment.id,
                public_reference="REF-TEST",
                amount_cents=3000,
                reason_code="schema_validation",
                idempotency_key="refund_test_key",
            )

            plan = MembershipPlan(
                public_reference="PLAN-TEST",
                name="Test Plan",
                monthly_price_cents=10900,
                monthly_credit_grant=1,
                rollover_ceiling=3,
                currency="USD",
                effective_from=date(2026, 1, 1),
            )
            session.add(plan)
            await session.flush()
            membership = Membership(
                public_reference="MEM-TEST",
                customer_id=customer.id,
                plan_id=plan.id,
                status="active",
                starts_at=date(2026, 1, 1),
                terms_policy_id="POL-MEM",
                terms_version=2,
            )
            session.add(membership)
            await session.flush()
            grant = MembershipLedgerEntry(
                public_reference="LEDGER-GRANT-TEST",
                membership_id=membership.id,
                entry_type="grant",
                credit_delta=1,
                effective_at=now - timedelta(days=10),
                expires_at=now + timedelta(days=80),
                actor_type="system",
                actor_reference="membership_billing",
                reason_code="monthly_grant",
                idempotency_key="ledger_grant_test",
            )
            consumption = MembershipLedgerEntry(
                public_reference="LEDGER-CONSUME-TEST",
                membership_id=membership.id,
                entry_type="consume",
                credit_delta=-1,
                effective_at=now,
                related_appointment_id=appointment.id,
                actor_type="system",
                actor_reference="appointment_settlement",
                reason_code="service_completed",
                idempotency_key="ledger_consume_test",
            )
            session.add_all([grant, consumption])
            await session.flush()
            session.add(
                MembershipCreditAllocation(
                    consumption_entry_id=consumption.id,
                    grant_entry_id=grant.id,
                    quantity=1,
                )
            )

            policy = PolicyDocument(
                policy_id="POL-TEST",
                title="Schema Test Policy",
                policy_area="testing",
            )
            session.add(policy)
            await session.flush()
            version = PolicyVersion(
                policy_document_id=policy.id,
                version=1,
                effective_from=date(2026, 1, 1),
                status="active",
                scope={"locations": ["all"]},
                source_path="business_spec/policies/POL-TEST-v1.md",
                content_checksum="a" * 64,
            )
            session.add(version)
            await session.flush()
            session.add(
                PolicySection(
                    policy_version_id=version.id,
                    section_id="POL-TEST-v1#1",
                    heading="Purpose",
                    body="Validate policy storage and lexical indexing.",
                    sort_order=1,
                    content_checksum="b" * 64,
                )
            )
            await session.flush()

        await transaction.rollback()


async def test_database_constraints_reject_invalid_temporal_and_financial_state(database) -> None:
    async with database.engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection) as session:
            invalid_service = Service(
                public_reference="SVC-INVALID",
                name="Invalid Primary Service",
                category="massage",
                duration_minutes=0,
                base_price_cents=1000,
                currency="USD",
                qualification_code="massage-core",
                is_add_on=False,
                active=True,
            )
            session.add(invalid_service)
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
        if transaction.is_active:
            await transaction.rollback()


async def test_refund_service_rejects_amount_above_remaining_capture(database) -> None:
    async with database.engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            location = Location(
                public_reference="LOC-REFUND-TEST",
                name="Refund Test",
                timezone="America/Chicago",
                currency="USD",
                active=True,
            )
            customer = Customer(
                public_reference="CUS-REFUND-TEST",
                first_name="Refund",
                last_name="Test",
                email="refund-test@example.test",
                email_verified=True,
                phone_verified=False,
                active=True,
            )
            session.add_all([location, customer])
            await session.flush()
            invoice = Invoice(
                public_reference="INV-REFUND-TEST",
                customer_id=customer.id,
                status="paid",
                total_cents=8000,
                currency="USD",
            )
            session.add(invoice)
            await session.flush()
            payment = Payment(
                public_reference="PAY-REFUND-TEST",
                invoice_id=invoice.id,
                customer_id=customer.id,
                obligation_reference=invoice.public_reference,
                status="captured",
                tender_type="card",
                amount_cents=8000,
                authorized_amount_cents=8000,
                captured_amount_cents=8000,
                refunded_amount_cents=0,
                currency="USD",
            )
            session.add(payment)
            await session.flush()

            with pytest.raises(RefundValidationError, match="exceeds remaining"):
                await create_pending_refund(
                    session,
                    payment_id=payment.id,
                    public_reference="REF-TOO-LARGE",
                    amount_cents=8001,
                    reason_code="invalid_test",
                    idempotency_key="refund_too_large",
                )

        await transaction.rollback()
