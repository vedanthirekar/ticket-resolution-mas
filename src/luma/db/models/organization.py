from __future__ import annotations

from datetime import date, datetime, time
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
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from luma.db.base import Base
from luma.db.models.common import TimestampMixin, UuidPrimaryKeyMixin


class Location(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("char_length(currency) = 3", name="currency_iso_length"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LocationBusinessHours(UuidPrimaryKeyMixin, Base):
    __tablename__ = "location_business_hours"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="valid_day_of_week"),
        CheckConstraint("opens_at < closes_at", name="opens_before_closes"),
        CheckConstraint(
            "valid_through IS NULL OR valid_through >= valid_from",
            name="valid_effective_dates",
        ),
        UniqueConstraint("location_id", "day_of_week", "valid_from"),
        {"schema": "business"},
    )

    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.locations.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    opens_at: Mapped[time] = mapped_column(Time, nullable=False)
    closes_at: Mapped[time] = mapped_column(Time, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_through: Mapped[date | None] = mapped_column(Date)


class Employee(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = ({"schema": "business"},)

    public_reference: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(48), nullable=False)
    home_location_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.locations.id"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EmployeeLocation(UuidPrimaryKeyMixin, Base):
    __tablename__ = "employee_locations"
    __table_args__ = (
        CheckConstraint(
            "valid_through IS NULL OR valid_through >= valid_from",
            name="valid_effective_dates",
        ),
        UniqueConstraint("employee_id", "location_id", "valid_from"),
        {"schema": "business"},
    )

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.employees.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.locations.id", ondelete="CASCADE"), nullable=False
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_through: Mapped[date | None] = mapped_column(Date)


class Service(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("duration_minutes >= 0", name="nonnegative_duration"),
        CheckConstraint(
            "is_add_on OR duration_minutes > 0", name="primary_service_positive_duration"
        ),
        CheckConstraint("base_price_cents >= 0", name="nonnegative_price"),
        CheckConstraint("credit_cost IS NULL OR credit_cost > 0", name="positive_credit_cost"),
        CheckConstraint("char_length(currency) = 3", name="currency_iso_length"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    base_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    credit_cost: Mapped[int | None] = mapped_column(Integer)
    qualification_code: Mapped[str] = mapped_column(String(64), nullable=False)
    required_resource_type: Mapped[str | None] = mapped_column(String(64))
    is_add_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LocationService(UuidPrimaryKeyMixin, Base):
    __tablename__ = "location_services"
    __table_args__ = (
        CheckConstraint(
            "valid_through IS NULL OR valid_through >= valid_from",
            name="valid_effective_dates",
        ),
        CheckConstraint(
            "price_override_cents IS NULL OR price_override_cents >= 0",
            name="nonnegative_price_override",
        ),
        UniqueConstraint("location_id", "service_id", "valid_from"),
        {"schema": "business"},
    )

    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.locations.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.services.id", ondelete="CASCADE"), nullable=False
    )
    offered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    price_override_cents: Mapped[int | None] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_through: Mapped[date | None] = mapped_column(Date)


class EmployeeService(UuidPrimaryKeyMixin, Base):
    __tablename__ = "employee_services"
    __table_args__ = (
        CheckConstraint(
            "valid_through IS NULL OR valid_through >= valid_from",
            name="valid_effective_dates",
        ),
        UniqueConstraint("employee_id", "service_id", "valid_from"),
        {"schema": "business"},
    )

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.employees.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.services.id", ondelete="CASCADE"), nullable=False
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_through: Mapped[date | None] = mapped_column(Date)


class EmployeeSchedule(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employee_schedules"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint("schedule_type IN ('available', 'blocked')", name="valid_schedule_type"),
        Index("ix_employee_schedules_employee_range", "employee_id", "starts_at", "ends_at"),
        {"schema": "business"},
    )

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.employees.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[UUID] = mapped_column(ForeignKey("business.locations.id"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(24), nullable=False, default="available")
    reason_code: Mapped[str | None] = mapped_column(String(64))


class Customer(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL", name="at_least_one_contact_channel"
        ),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
