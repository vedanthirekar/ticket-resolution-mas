from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from luma.db.base import Base
from luma.db.models.common import CreatedAtMixin, TimestampMixin, UuidPrimaryKeyMixin


class Invoice(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("total_cents >= 0", name="nonnegative_total"),
        CheckConstraint("char_length(currency) = 3", name="currency_iso_length"),
        CheckConstraint(
            "status IN ('draft', 'open', 'paid', 'partially_paid', 'voided')",
            name="valid_status",
        ),
        Index("ix_invoices_customer_created", "customer_id", "created_at"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("business.customers.id"), nullable=False)
    appointment_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.appointments.id"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")


class InvoiceItem(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="nonnegative_amount"),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("char_length(currency) = 3", name="currency_iso_length"),
        CheckConstraint(
            "item_type IN ('primary_service', 'add_on', 'cancellation_fee', "
            "'no_show_fee', 'tax', 'gratuity', 'other')",
            name="valid_item_type",
        ),
        Index("ix_invoice_items_appointment", "appointment_id"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.invoices.id", ondelete="CASCADE"), nullable=False
    )
    appointment_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.appointments.id"))
    service_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.services.id"))
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")


class Payment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="nonnegative_amount"),
        CheckConstraint("authorized_amount_cents >= 0", name="nonnegative_authorized"),
        CheckConstraint("captured_amount_cents >= 0", name="nonnegative_captured"),
        CheckConstraint("refunded_amount_cents >= 0", name="nonnegative_refunded"),
        CheckConstraint(
            "refunded_amount_cents <= captured_amount_cents",
            name="refund_not_above_capture",
        ),
        CheckConstraint("char_length(currency) = 3", name="currency_iso_length"),
        CheckConstraint(
            "status IN ('created', 'authorized', 'captured', 'partially_refunded', "
            "'refunded', 'voided', 'failed')",
            name="valid_status",
        ),
        CheckConstraint("tender_type IN ('card', 'cash', 'other')", name="valid_tender_type"),
        Index("ix_payments_invoice_created", "invoice_id", "created_at"),
        Index("ix_payments_customer_created", "customer_id", "created_at"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("business.invoices.id"), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("business.customers.id"), nullable=False)
    obligation_reference: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    tender_type: Mapped[str] = mapped_column(String(24), nullable=False, default="card")
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    authorized_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captured_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refunded_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    processor_reference: Mapped[str | None] = mapped_column(String(128), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)


class PaymentEvent(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="nonnegative_amount"),
        CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'external_provider')",
            name="valid_actor_type",
        ),
        Index("ix_payment_events_payment_occurred", "payment_id", "occurred_at", "id"),
        UniqueConstraint("payment_id", "processor_event_reference"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.payments.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processor_event_reference: Mapped[str | None] = mapped_column(String(128))
    correlation_reference: Mapped[str | None] = mapped_column(String(64), index=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )


class Refund(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="positive_amount"),
        CheckConstraint("status IN ('pending', 'succeeded', 'failed')", name="valid_status"),
        Index("ix_refunds_payment_status", "payment_id", "status"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("business.payments.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    processor_reference: Mapped[str | None] = mapped_column(String(128), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
