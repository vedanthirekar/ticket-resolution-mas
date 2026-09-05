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


class Appointment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("scheduled_end > scheduled_start", name="ends_after_starts"),
        CheckConstraint("quoted_price_cents >= 0", name="nonnegative_quoted_price"),
        CheckConstraint(
            "quoted_credit_cost IS NULL OR quoted_credit_cost > 0",
            name="positive_quoted_credit_cost",
        ),
        CheckConstraint("char_length(currency) = 3", name="currency_iso_length"),
        CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'checked_in', 'completed', "
            "'cancelled', 'no_show')",
            name="valid_status",
        ),
        CheckConstraint(
            "booking_channel IN ('web', 'mobile', 'phone', 'front_desk', 'internal')",
            name="valid_booking_channel",
        ),
        Index("ix_appointments_customer_start", "customer_id", "scheduled_start"),
        Index("ix_appointments_employee_start", "employee_id", "scheduled_start"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("business.customers.id"), nullable=False)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("business.locations.id"), nullable=False)
    service_id: Mapped[UUID] = mapped_column(ForeignKey("business.services.id"), nullable=False)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("business.employees.id"), nullable=False)
    predecessor_appointment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business.appointments.id"), unique=True
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quoted_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quoted_credit_cost: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled")
    booking_channel: Mapped[str] = mapped_column(String(24), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_cancellation_reason: Mapped[str | None] = mapped_column(String(64))


class AppointmentEvent(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "appointment_events"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'external_provider')",
            name="valid_actor_type",
        ),
        CheckConstraint(
            "initiating_party IN ('customer', 'provider', 'business', 'system', "
            "'unknown', 'not_applicable')",
            name="valid_initiating_party",
        ),
        CheckConstraint(
            "channel IN ('web', 'mobile', 'phone', 'front_desk', 'batch', "
            "'provider_webhook', 'internal')",
            name="valid_channel",
        ),
        Index(
            "ix_appointment_events_appointment_occurred",
            "appointment_id",
            "occurred_at",
            "id",
        ),
        UniqueConstraint("appointment_id", "external_reference"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    appointment_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.appointments.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    initiating_party: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    correlation_reference: Mapped[str | None] = mapped_column(String(64), index=True)
    external_reference: Mapped[str | None] = mapped_column(String(128))
    causation_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business.appointment_events.id")
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
