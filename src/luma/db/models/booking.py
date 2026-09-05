from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from luma.db.base import Base
from luma.db.models.common import TimestampMixin, UuidPrimaryKeyMixin


class BookingSetting(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "booking_settings"
    __table_args__ = (
        CheckConstraint("minimum_lead_minutes >= 0", name="nonnegative_lead_time"),
        CheckConstraint("booking_horizon_days > 0", name="positive_booking_horizon"),
        CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name="valid_effective_dates",
        ),
        UniqueConstraint("effective_from"),
        {"schema": "business"},
    )

    minimum_lead_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    booking_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_through: Mapped[date | None] = mapped_column(Date)


class LocationServiceSetting(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "location_service_settings"
    __table_args__ = (
        CheckConstraint(
            "minimum_lead_minutes IS NULL OR minimum_lead_minutes >= 0",
            name="nonnegative_lead_time",
        ),
        CheckConstraint(
            "booking_horizon_days IS NULL OR booking_horizon_days > 0",
            name="positive_booking_horizon",
        ),
        CheckConstraint(
            "resource_capacity IS NULL OR resource_capacity > 0", name="positive_capacity"
        ),
        CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name="valid_effective_dates",
        ),
        UniqueConstraint("location_id", "service_id", "effective_from"),
        {"schema": "business"},
    )

    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.locations.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.services.id", ondelete="CASCADE"), nullable=False
    )
    online_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    minimum_lead_minutes: Mapped[int | None] = mapped_column(Integer)
    booking_horizon_days: Mapped[int | None] = mapped_column(Integer)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_capacity: Mapped[int | None] = mapped_column(Integer)
    eligibility_rule: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_through: Mapped[date | None] = mapped_column(Date)


class EmployeeBookingSetting(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employee_booking_settings"
    __table_args__ = (
        CheckConstraint(
            "minimum_lead_minutes IS NULL OR minimum_lead_minutes >= 0",
            name="nonnegative_lead_time",
        ),
        CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name="valid_effective_dates",
        ),
        Index(
            "uq_employee_booking_settings_default",
            "employee_id",
            "effective_from",
            unique=True,
            postgresql_where=text("service_id IS NULL"),
        ),
        UniqueConstraint("employee_id", "service_id", "effective_from"),
        {"schema": "business"},
    )

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.employees.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business.services.id", ondelete="CASCADE")
    )
    online_enabled: Mapped[bool | None] = mapped_column(Boolean)
    minimum_lead_minutes: Mapped[int | None] = mapped_column(Integer)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_through: Mapped[date | None] = mapped_column(Date)


class LocationResource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "location_resources"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="positive_capacity"),
        UniqueConstraint("location_id", "public_reference"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.locations.id", ondelete="CASCADE"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BookingBlock(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "booking_blocks"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint(
            "location_id IS NOT NULL OR employee_id IS NOT NULL OR service_id IS NOT NULL "
            "OR resource_id IS NOT NULL",
            name="has_block_scope",
        ),
        Index("ix_booking_blocks_range", "starts_at", "ends_at"),
        {"schema": "business"},
    )

    location_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.locations.id"))
    employee_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.employees.id"))
    service_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.services.id"))
    resource_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.location_resources.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)


class BookingAttempt(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "booking_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'validating', 'committed', 'rejected', 'failed')",
            name="valid_status",
        ),
        CheckConstraint(
            "(status = 'committed' AND appointment_id IS NOT NULL) "
            "OR (status <> 'committed' AND appointment_id IS NULL)",
            name="committed_has_appointment",
        ),
        Index("ix_booking_attempts_customer_created", "customer_id", "created_at"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    correlation_reference: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("business.customers.id"), nullable=False)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("business.locations.id"), nullable=False)
    service_id: Mapped[UUID] = mapped_column(ForeignKey("business.services.id"), nullable=False)
    requested_employee_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.employees.id"))
    requested_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    appointment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business.appointments.id"), unique=True
    )
