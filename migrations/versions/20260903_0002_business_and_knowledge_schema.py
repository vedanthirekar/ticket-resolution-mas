"""Create Luma operational and policy schemas.

Revision ID: 20260903_0002
Revises: 20260903_0001
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0002"
down_revision: str | None = "20260903_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[object]:
    return sa.Column(
        "id",
        sa.Uuid(),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _created_at() -> sa.Column[object]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _updated_at() -> sa.Column[object]:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return _created_at(), _updated_at()


def upgrade() -> None:
    op.execute("CREATE SCHEMA business")
    op.execute("CREATE SCHEMA knowledge")

    op.create_table(
        "locations",
        _id(),
        sa.Column("public_reference", sa.String(24), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "char_length(currency) = 3", name=op.f("ck_locations_currency_iso_length")
        ),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
        sa.UniqueConstraint("public_reference", name="uq_locations_public_reference"),
        schema="business",
    )

    op.create_table(
        "location_business_hours",
        _id(),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_through", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "day_of_week BETWEEN 0 AND 6",
            name=op.f("ck_location_business_hours_valid_day_of_week"),
        ),
        sa.CheckConstraint(
            "opens_at < closes_at", name=op.f("ck_location_business_hours_opens_before_closes")
        ),
        sa.CheckConstraint(
            "valid_through IS NULL OR valid_through >= valid_from",
            name=op.f("ck_location_business_hours_valid_effective_dates"),
        ),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_location_business_hours"),
        sa.UniqueConstraint(
            "location_id",
            "day_of_week",
            "valid_from",
            name="uq_location_business_hours_location_id",
        ),
        schema="business",
    )

    op.create_table(
        "employees",
        _id(),
        sa.Column("public_reference", sa.String(24), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(48), nullable=False),
        sa.Column("home_location_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["home_location_id"], ["business.locations.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_employees"),
        sa.UniqueConstraint("public_reference", name="uq_employees_public_reference"),
        schema="business",
    )

    op.create_table(
        "employee_locations",
        _id(),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_through", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "valid_through IS NULL OR valid_through >= valid_from",
            name=op.f("ck_employee_locations_valid_effective_dates"),
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["business.employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_employee_locations"),
        sa.UniqueConstraint(
            "employee_id", "location_id", "valid_from", name="uq_employee_locations_employee_id"
        ),
        schema="business",
    )

    op.create_table(
        "services",
        _id(),
        sa.Column("public_reference", sa.String(24), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("base_price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("credit_cost", sa.Integer(), nullable=True),
        sa.Column("qualification_code", sa.String(64), nullable=False),
        sa.Column("required_resource_type", sa.String(64), nullable=True),
        sa.Column("is_add_on", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("base_price_cents >= 0", name=op.f("ck_services_nonnegative_price")),
        sa.CheckConstraint(
            "char_length(currency) = 3", name=op.f("ck_services_currency_iso_length")
        ),
        sa.CheckConstraint(
            "credit_cost IS NULL OR credit_cost > 0", name=op.f("ck_services_positive_credit_cost")
        ),
        sa.CheckConstraint("duration_minutes >= 0", name=op.f("ck_services_nonnegative_duration")),
        sa.CheckConstraint(
            "is_add_on OR duration_minutes > 0",
            name=op.f("ck_services_primary_service_positive_duration"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_services"),
        sa.UniqueConstraint("public_reference", name="uq_services_public_reference"),
        schema="business",
    )

    op.create_table(
        "location_services",
        _id(),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("offered", sa.Boolean(), nullable=False),
        sa.Column("price_override_cents", sa.Integer(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_through", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "price_override_cents IS NULL OR price_override_cents >= 0",
            name=op.f("ck_location_services_nonnegative_price_override"),
        ),
        sa.CheckConstraint(
            "valid_through IS NULL OR valid_through >= valid_from",
            name=op.f("ck_location_services_valid_effective_dates"),
        ),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["business.services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_location_services"),
        sa.UniqueConstraint(
            "location_id", "service_id", "valid_from", name="uq_location_services_location_id"
        ),
        schema="business",
    )

    op.create_table(
        "employee_services",
        _id(),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_through", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "valid_through IS NULL OR valid_through >= valid_from",
            name=op.f("ck_employee_services_valid_effective_dates"),
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["business.employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["business.services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_employee_services"),
        sa.UniqueConstraint(
            "employee_id", "service_id", "valid_from", name="uq_employee_services_employee_id"
        ),
        schema="business",
    )

    op.create_table(
        "employee_schedules",
        _id(),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schedule_type", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "ends_at > starts_at", name=op.f("ck_employee_schedules_ends_after_starts")
        ),
        sa.CheckConstraint(
            "schedule_type IN ('available', 'blocked')",
            name=op.f("ck_employee_schedules_valid_schedule_type"),
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["business.employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_employee_schedules"),
        schema="business",
    )
    op.create_index(
        "ix_employee_schedules_employee_range",
        "employee_schedules",
        ["employee_id", "starts_at", "ends_at"],
        schema="business",
    )

    op.create_table(
        "customers",
        _id(),
        sa.Column("public_reference", sa.String(24), nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name=op.f("ck_customers_at_least_one_contact_channel"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
        sa.UniqueConstraint("email", name="uq_customers_email"),
        sa.UniqueConstraint("phone", name="uq_customers_phone"),
        sa.UniqueConstraint("public_reference", name="uq_customers_public_reference"),
        schema="business",
    )

    op.create_table(
        "appointments",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("predecessor_appointment_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quoted_price_cents", sa.Integer(), nullable=False),
        sa.Column("quoted_credit_cost", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("booking_channel", sa.String(24), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_cancellation_reason", sa.String(64), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "booking_channel IN ('web', 'mobile', 'phone', 'front_desk', 'internal')",
            name=op.f("ck_appointments_valid_booking_channel"),
        ),
        sa.CheckConstraint(
            "char_length(currency) = 3", name=op.f("ck_appointments_currency_iso_length")
        ),
        sa.CheckConstraint(
            "quoted_credit_cost IS NULL OR quoted_credit_cost > 0",
            name=op.f("ck_appointments_positive_quoted_credit_cost"),
        ),
        sa.CheckConstraint(
            "quoted_price_cents >= 0", name=op.f("ck_appointments_nonnegative_quoted_price")
        ),
        sa.CheckConstraint(
            "scheduled_end > scheduled_start", name=op.f("ck_appointments_ends_after_starts")
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'checked_in', 'completed', "
            "'cancelled', 'no_show')",
            name=op.f("ck_appointments_valid_status"),
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["business.customers.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["business.employees.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"]),
        sa.ForeignKeyConstraint(["predecessor_appointment_id"], ["business.appointments.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["business.services.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_appointments"),
        sa.UniqueConstraint(
            "predecessor_appointment_id", name="uq_appointments_predecessor_appointment_id"
        ),
        sa.UniqueConstraint("public_reference", name="uq_appointments_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_appointments_customer_start",
        "appointments",
        ["customer_id", "scheduled_start"],
        schema="business",
    )
    op.create_index(
        "ix_appointments_employee_start",
        "appointments",
        ["employee_id", "scheduled_start"],
        schema="business",
    )

    op.create_table(
        "appointment_events",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(24), nullable=False),
        sa.Column("actor_reference", sa.String(64), nullable=False),
        sa.Column("initiating_party", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("correlation_reference", sa.String(64), nullable=True),
        sa.Column("external_reference", sa.String(128), nullable=True),
        sa.Column("causation_event_id", sa.Uuid(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _created_at(),
        sa.CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'external_provider')",
            name=op.f("ck_appointment_events_valid_actor_type"),
        ),
        sa.CheckConstraint(
            "channel IN ('web', 'mobile', 'phone', 'front_desk', 'batch', "
            "'provider_webhook', 'internal')",
            name=op.f("ck_appointment_events_valid_channel"),
        ),
        sa.CheckConstraint(
            "initiating_party IN ('customer', 'provider', 'business', 'system', "
            "'unknown', 'not_applicable')",
            name=op.f("ck_appointment_events_valid_initiating_party"),
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"], ["business.appointments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["causation_event_id"], ["business.appointment_events.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_appointment_events"),
        sa.UniqueConstraint(
            "appointment_id",
            "external_reference",
            name="uq_appointment_events_appointment_id",
        ),
        sa.UniqueConstraint("public_reference", name="uq_appointment_events_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_appointment_events_appointment_occurred",
        "appointment_events",
        ["appointment_id", "occurred_at", "id"],
        schema="business",
    )
    op.create_index(
        "ix_business_appointment_events_correlation_reference",
        "appointment_events",
        ["correlation_reference"],
        schema="business",
    )

    op.create_table(
        "invoices",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "char_length(currency) = 3", name=op.f("ck_invoices_currency_iso_length")
        ),
        sa.CheckConstraint("total_cents >= 0", name=op.f("ck_invoices_nonnegative_total")),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'paid', 'partially_paid', 'voided')",
            name=op.f("ck_invoices_valid_status"),
        ),
        sa.ForeignKeyConstraint(["appointment_id"], ["business.appointments.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["business.customers.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_invoices"),
        sa.UniqueConstraint("public_reference", name="uq_invoices_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_invoices_customer_created",
        "invoices",
        ["customer_id", "created_at"],
        schema="business",
    )

    op.create_table(
        "invoice_items",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("description", sa.String(240), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        _created_at(),
        sa.CheckConstraint("amount_cents >= 0", name=op.f("ck_invoice_items_nonnegative_amount")),
        sa.CheckConstraint(
            "char_length(currency) = 3", name=op.f("ck_invoice_items_currency_iso_length")
        ),
        sa.CheckConstraint(
            "item_type IN ('primary_service', 'add_on', 'cancellation_fee', "
            "'no_show_fee', 'tax', 'gratuity', 'other')",
            name=op.f("ck_invoice_items_valid_item_type"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_invoice_items_positive_quantity")),
        sa.ForeignKeyConstraint(["appointment_id"], ["business.appointments.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["business.invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["business.services.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_items"),
        sa.UniqueConstraint("public_reference", name="uq_invoice_items_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_invoice_items_appointment",
        "invoice_items",
        ["appointment_id"],
        schema="business",
    )

    op.create_table(
        "payments",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("obligation_reference", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("tender_type", sa.String(24), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("authorized_amount_cents", sa.Integer(), nullable=False),
        sa.Column("captured_amount_cents", sa.Integer(), nullable=False),
        sa.Column("refunded_amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("processor_reference", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("amount_cents >= 0", name=op.f("ck_payments_nonnegative_amount")),
        sa.CheckConstraint(
            "authorized_amount_cents >= 0", name=op.f("ck_payments_nonnegative_authorized")
        ),
        sa.CheckConstraint(
            "captured_amount_cents >= 0", name=op.f("ck_payments_nonnegative_captured")
        ),
        sa.CheckConstraint(
            "refunded_amount_cents >= 0", name=op.f("ck_payments_nonnegative_refunded")
        ),
        sa.CheckConstraint(
            "refunded_amount_cents <= captured_amount_cents",
            name=op.f("ck_payments_refund_not_above_capture"),
        ),
        sa.CheckConstraint(
            "char_length(currency) = 3", name=op.f("ck_payments_currency_iso_length")
        ),
        sa.CheckConstraint(
            "status IN ('created', 'authorized', 'captured', 'partially_refunded', "
            "'refunded', 'voided', 'failed')",
            name=op.f("ck_payments_valid_status"),
        ),
        sa.CheckConstraint(
            "tender_type IN ('card', 'cash', 'other')",
            name=op.f("ck_payments_valid_tender_type"),
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["business.customers.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["business.invoices.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        sa.UniqueConstraint("processor_reference", name="uq_payments_processor_reference"),
        sa.UniqueConstraint("public_reference", name="uq_payments_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_business_payments_obligation_reference",
        "payments",
        ["obligation_reference"],
        schema="business",
    )
    op.create_index(
        "ix_payments_customer_created",
        "payments",
        ["customer_id", "created_at"],
        schema="business",
    )
    op.create_index(
        "ix_payments_invoice_created",
        "payments",
        ["invoice_id", "created_at"],
        schema="business",
    )

    op.create_table(
        "payment_events",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(24), nullable=False),
        sa.Column("actor_reference", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processor_event_reference", sa.String(128), nullable=True),
        sa.Column("correlation_reference", sa.String(64), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _created_at(),
        sa.CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'external_provider')",
            name=op.f("ck_payment_events_valid_actor_type"),
        ),
        sa.CheckConstraint("amount_cents >= 0", name=op.f("ck_payment_events_nonnegative_amount")),
        sa.ForeignKeyConstraint(["payment_id"], ["business.payments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_payment_events"),
        sa.UniqueConstraint(
            "payment_id",
            "processor_event_reference",
            name="uq_payment_events_payment_id",
        ),
        sa.UniqueConstraint("public_reference", name="uq_payment_events_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_business_payment_events_correlation_reference",
        "payment_events",
        ["correlation_reference"],
        schema="business",
    )
    op.create_index(
        "ix_payment_events_payment_occurred",
        "payment_events",
        ["payment_id", "occurred_at", "id"],
        schema="business",
    )

    op.create_table(
        "refunds",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("processor_reference", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("amount_cents > 0", name=op.f("ck_refunds_positive_amount")),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')", name=op.f("ck_refunds_valid_status")
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["business.payments.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_refunds"),
        sa.UniqueConstraint("idempotency_key", name="uq_refunds_idempotency_key"),
        sa.UniqueConstraint("processor_reference", name="uq_refunds_processor_reference"),
        sa.UniqueConstraint("public_reference", name="uq_refunds_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_refunds_payment_status",
        "refunds",
        ["payment_id", "status"],
        schema="business",
    )

    op.create_table(
        "membership_plans",
        _id(),
        sa.Column("public_reference", sa.String(24), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("monthly_price_cents", sa.Integer(), nullable=False),
        sa.Column("monthly_credit_grant", sa.Integer(), nullable=False),
        sa.Column("rollover_ceiling", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_through", sa.Date(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "char_length(currency) = 3", name=op.f("ck_membership_plans_currency_iso_length")
        ),
        sa.CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name=op.f("ck_membership_plans_valid_effective_dates"),
        ),
        sa.CheckConstraint(
            "monthly_credit_grant > 0", name=op.f("ck_membership_plans_positive_credit_grant")
        ),
        sa.CheckConstraint(
            "monthly_price_cents > 0", name=op.f("ck_membership_plans_positive_monthly_price")
        ),
        sa.CheckConstraint(
            "rollover_ceiling >= monthly_credit_grant",
            name=op.f("ck_membership_plans_valid_rollover_ceiling"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_membership_plans"),
        sa.UniqueConstraint(
            "public_reference", "effective_from", name="uq_membership_plans_public_reference"
        ),
        schema="business",
    )

    op.create_table(
        "memberships",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("starts_at", sa.Date(), nullable=False),
        sa.Column("ends_at", sa.Date(), nullable=True),
        sa.Column("next_renewal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_policy_id", sa.String(32), nullable=False),
        sa.Column("terms_version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name=op.f("ck_memberships_valid_membership_dates"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'cancelled', 'expired')",
            name=op.f("ck_memberships_valid_status"),
        ),
        sa.CheckConstraint("terms_version > 0", name=op.f("ck_memberships_positive_terms_version")),
        sa.ForeignKeyConstraint(["customer_id"], ["business.customers.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["business.membership_plans.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_memberships"),
        sa.UniqueConstraint("public_reference", name="uq_memberships_public_reference"),
        schema="business",
    )
    op.create_index(
        "uq_memberships_customer_current",
        "memberships",
        ["customer_id"],
        unique=True,
        schema="business",
        postgresql_where=sa.text("status IN ('active', 'paused')"),
    )

    op.create_table(
        "membership_ledger",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(24), nullable=False),
        sa.Column("credit_delta", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_appointment_id", sa.Uuid(), nullable=True),
        sa.Column("related_entry_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(24), nullable=False),
        sa.Column("actor_reference", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("approval_reference", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "(entry_type = 'grant' AND credit_delta > 0) OR entry_type <> 'grant'",
            name=op.f("ck_membership_ledger_grant_is_positive"),
        ),
        sa.CheckConstraint(
            "(entry_type IN ('consume', 'expire') AND credit_delta < 0) "
            "OR entry_type NOT IN ('consume', 'expire')",
            name=op.f("ck_membership_ledger_consumption_and_expiry_negative"),
        ),
        sa.CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'external_provider')",
            name=op.f("ck_membership_ledger_valid_actor_type"),
        ),
        sa.CheckConstraint(
            "credit_delta <> 0", name=op.f("ck_membership_ledger_nonzero_credit_delta")
        ),
        sa.CheckConstraint(
            "entry_type IN ('grant', 'consume', 'expire', 'correction', 'reversal')",
            name=op.f("ck_membership_ledger_valid_entry_type"),
        ),
        sa.ForeignKeyConstraint(["membership_id"], ["business.memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_appointment_id"], ["business.appointments.id"]),
        sa.ForeignKeyConstraint(["related_entry_id"], ["business.membership_ledger.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_membership_ledger"),
        sa.UniqueConstraint("idempotency_key", name="uq_membership_ledger_idempotency_key"),
        sa.UniqueConstraint("public_reference", name="uq_membership_ledger_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_membership_ledger_membership_effective",
        "membership_ledger",
        ["membership_id", "effective_at", "id"],
        schema="business",
    )

    op.create_table(
        "membership_credit_allocations",
        _id(),
        sa.Column("consumption_entry_id", sa.Uuid(), nullable=False),
        sa.Column("grant_entry_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_membership_credit_allocations_positive_quantity")
        ),
        sa.ForeignKeyConstraint(
            ["consumption_entry_id"],
            ["business.membership_ledger.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grant_entry_id"], ["business.membership_ledger.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_membership_credit_allocations"),
        sa.UniqueConstraint(
            "consumption_entry_id",
            "grant_entry_id",
            name="uq_membership_credit_allocations_consumption_entry_id",
        ),
        schema="business",
    )

    op.create_table(
        "booking_settings",
        _id(),
        sa.Column("minimum_lead_minutes", sa.Integer(), nullable=False),
        sa.Column("booking_horizon_days", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_through", sa.Date(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "booking_horizon_days > 0", name=op.f("ck_booking_settings_positive_booking_horizon")
        ),
        sa.CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name=op.f("ck_booking_settings_valid_effective_dates"),
        ),
        sa.CheckConstraint(
            "minimum_lead_minutes >= 0", name=op.f("ck_booking_settings_nonnegative_lead_time")
        ),
        sa.PrimaryKeyConstraint("id", name="pk_booking_settings"),
        sa.UniqueConstraint("effective_from", name="uq_booking_settings_effective_from"),
        schema="business",
    )

    op.create_table(
        "location_service_settings",
        _id(),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("online_enabled", sa.Boolean(), nullable=False),
        sa.Column("minimum_lead_minutes", sa.Integer(), nullable=True),
        sa.Column("booking_horizon_days", sa.Integer(), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_capacity", sa.Integer(), nullable=True),
        sa.Column(
            "eligibility_rule",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_through", sa.Date(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "booking_horizon_days IS NULL OR booking_horizon_days > 0",
            name=op.f("ck_location_service_settings_positive_booking_horizon"),
        ),
        sa.CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name=op.f("ck_location_service_settings_valid_effective_dates"),
        ),
        sa.CheckConstraint(
            "minimum_lead_minutes IS NULL OR minimum_lead_minutes >= 0",
            name=op.f("ck_location_service_settings_nonnegative_lead_time"),
        ),
        sa.CheckConstraint(
            "resource_capacity IS NULL OR resource_capacity > 0",
            name=op.f("ck_location_service_settings_positive_capacity"),
        ),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["business.services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_location_service_settings"),
        sa.UniqueConstraint(
            "location_id",
            "service_id",
            "effective_from",
            name="uq_location_service_settings_location_id",
        ),
        schema="business",
    )

    op.create_table(
        "employee_booking_settings",
        _id(),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("online_enabled", sa.Boolean(), nullable=True),
        sa.Column("minimum_lead_minutes", sa.Integer(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_through", sa.Date(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name=op.f("ck_employee_booking_settings_valid_effective_dates"),
        ),
        sa.CheckConstraint(
            "minimum_lead_minutes IS NULL OR minimum_lead_minutes >= 0",
            name=op.f("ck_employee_booking_settings_nonnegative_lead_time"),
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["business.employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["business.services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_employee_booking_settings"),
        sa.UniqueConstraint(
            "employee_id",
            "service_id",
            "effective_from",
            name="uq_employee_booking_settings_employee_id",
        ),
        schema="business",
    )
    op.create_index(
        "uq_employee_booking_settings_default",
        "employee_booking_settings",
        ["employee_id", "effective_from"],
        unique=True,
        schema="business",
        postgresql_where=sa.text("service_id IS NULL"),
    )

    op.create_table(
        "location_resources",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("capacity > 0", name=op.f("ck_location_resources_positive_capacity")),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_location_resources"),
        sa.UniqueConstraint(
            "location_id", "public_reference", name="uq_location_resources_location_id"
        ),
        sa.UniqueConstraint("public_reference", name="uq_location_resources_public_reference"),
        schema="business",
    )

    op.create_table(
        "booking_blocks",
        _id(),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_booking_blocks_ends_after_starts")),
        sa.CheckConstraint(
            "location_id IS NOT NULL OR employee_id IS NOT NULL OR service_id IS NOT NULL "
            "OR resource_id IS NOT NULL",
            name=op.f("ck_booking_blocks_has_block_scope"),
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["business.employees.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["business.location_resources.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["business.services.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_booking_blocks"),
        schema="business",
    )
    op.create_index(
        "ix_booking_blocks_range",
        "booking_blocks",
        ["starts_at", "ends_at"],
        schema="business",
    )

    op.create_table(
        "booking_attempts",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("correlation_reference", sa.String(64), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("requested_employee_id", sa.Uuid(), nullable=True),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "(status = 'committed' AND appointment_id IS NOT NULL) "
            "OR (status <> 'committed' AND appointment_id IS NULL)",
            name=op.f("ck_booking_attempts_committed_has_appointment"),
        ),
        sa.CheckConstraint(
            "status IN ('received', 'validating', 'committed', 'rejected', 'failed')",
            name=op.f("ck_booking_attempts_valid_status"),
        ),
        sa.ForeignKeyConstraint(["appointment_id"], ["business.appointments.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["business.customers.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["business.locations.id"]),
        sa.ForeignKeyConstraint(["requested_employee_id"], ["business.employees.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["business.services.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_booking_attempts"),
        sa.UniqueConstraint("appointment_id", name="uq_booking_attempts_appointment_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_booking_attempts_idempotency_key"),
        sa.UniqueConstraint("public_reference", name="uq_booking_attempts_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_booking_attempts_customer_created",
        "booking_attempts",
        ["customer_id", "created_at"],
        schema="business",
    )
    op.create_index(
        "ix_business_booking_attempts_correlation_reference",
        "booking_attempts",
        ["correlation_reference"],
        schema="business",
    )

    op.create_table(
        "audit_events",
        _id(),
        sa.Column("public_reference", sa.String(32), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_reference", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(24), nullable=False),
        sa.Column("actor_reference", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("correlation_reference", sa.String(64), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'external_provider')",
            name=op.f("ck_audit_events_valid_actor_type"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
        sa.UniqueConstraint("public_reference", name="uq_audit_events_public_reference"),
        schema="business",
    )
    op.create_index(
        "ix_audit_events_target_occurred",
        "audit_events",
        ["target_type", "target_reference", "occurred_at"],
        schema="business",
    )
    op.create_index(
        "ix_business_audit_events_correlation_reference",
        "audit_events",
        ["correlation_reference"],
        schema="business",
    )

    op.create_table(
        "policy_documents",
        _id(),
        sa.Column("policy_id", sa.String(32), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("policy_area", sa.String(64), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_policy_documents"),
        sa.UniqueConstraint("policy_id", name="uq_policy_documents_policy_id"),
        schema="knowledge",
    )
    op.create_index(
        "ix_knowledge_policy_documents_policy_area",
        "policy_documents",
        ["policy_area"],
        schema="knowledge",
    )

    op.create_table(
        "policy_versions",
        _id(),
        sa.Column("policy_document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_through", sa.Date(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "scope",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("supersedes_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_path", sa.String(320), nullable=False),
        sa.Column("content_checksum", sa.String(64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name=op.f("ck_policy_versions_valid_effective_dates"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'superseded')",
            name=op.f("ck_policy_versions_valid_status"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_policy_versions_positive_version")),
        sa.ForeignKeyConstraint(
            ["policy_document_id"], ["knowledge.policy_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["supersedes_version_id"], ["knowledge.policy_versions.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_policy_versions"),
        sa.UniqueConstraint("content_checksum", name="uq_policy_versions_content_checksum"),
        sa.UniqueConstraint(
            "policy_document_id", "version", name="uq_policy_versions_policy_document_id"
        ),
        sa.UniqueConstraint("source_path", name="uq_policy_versions_source_path"),
        schema="knowledge",
    )

    op.create_table(
        "policy_sections",
        _id(),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.String(96), nullable=False),
        sa.Column("parent_section_id", sa.Uuid(), nullable=True),
        sa.Column("heading", sa.String(240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("content_checksum", sa.String(64), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(heading, '') || ' ' || coalesce(body, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_policy_sections_nonnegative_sort_order")
        ),
        sa.ForeignKeyConstraint(["parent_section_id"], ["knowledge.policy_sections.id"]),
        sa.ForeignKeyConstraint(
            ["policy_version_id"], ["knowledge.policy_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_sections"),
        sa.UniqueConstraint("section_id", name="uq_policy_sections_section_id"),
        sa.UniqueConstraint(
            "policy_version_id", "section_id", name="uq_policy_sections_policy_version_id"
        ),
        schema="knowledge",
    )
    op.create_index(
        "ix_policy_sections_search_vector",
        "policy_sections",
        ["search_vector"],
        schema="knowledge",
        postgresql_using="gin",
    )

    op.create_table(
        "policy_section_links",
        _id(),
        sa.Column("source_section_id", sa.Uuid(), nullable=False),
        sa.Column("target_section_id", sa.Uuid(), nullable=False),
        sa.Column("link_type", sa.String(24), nullable=False),
        sa.CheckConstraint(
            "source_section_id <> target_section_id",
            name=op.f("ck_policy_section_links_different_sections"),
        ),
        sa.CheckConstraint(
            "link_type IN ('references', 'exception_to', 'supersedes', 'related')",
            name=op.f("ck_policy_section_links_valid_link_type"),
        ),
        sa.ForeignKeyConstraint(
            ["source_section_id"], ["knowledge.policy_sections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_section_id"], ["knowledge.policy_sections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_section_links"),
        sa.UniqueConstraint(
            "source_section_id",
            "target_section_id",
            "link_type",
            name="uq_policy_section_links_source_section_id",
        ),
        schema="knowledge",
    )


def downgrade() -> None:
    tables = (
        ("knowledge", "policy_section_links"),
        ("knowledge", "policy_sections"),
        ("knowledge", "policy_versions"),
        ("knowledge", "policy_documents"),
        ("business", "audit_events"),
        ("business", "booking_attempts"),
        ("business", "booking_blocks"),
        ("business", "location_resources"),
        ("business", "employee_booking_settings"),
        ("business", "location_service_settings"),
        ("business", "booking_settings"),
        ("business", "membership_credit_allocations"),
        ("business", "membership_ledger"),
        ("business", "memberships"),
        ("business", "membership_plans"),
        ("business", "refunds"),
        ("business", "payment_events"),
        ("business", "payments"),
        ("business", "invoice_items"),
        ("business", "invoices"),
        ("business", "appointment_events"),
        ("business", "appointments"),
        ("business", "customers"),
        ("business", "employee_schedules"),
        ("business", "employee_services"),
        ("business", "location_services"),
        ("business", "services"),
        ("business", "employee_locations"),
        ("business", "employees"),
        ("business", "location_business_hours"),
        ("business", "locations"),
    )
    for schema, table in tables:
        op.drop_table(table, schema=schema)

    op.execute("DROP SCHEMA knowledge")
    op.execute("DROP SCHEMA business")
