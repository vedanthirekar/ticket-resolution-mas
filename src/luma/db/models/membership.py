from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from luma.db.base import Base
from luma.db.models.common import CreatedAtMixin, TimestampMixin, UuidPrimaryKeyMixin


class MembershipPlan(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "membership_plans"
    __table_args__ = (
        CheckConstraint("monthly_price_cents > 0", name="positive_monthly_price"),
        CheckConstraint("monthly_credit_grant > 0", name="positive_credit_grant"),
        CheckConstraint("rollover_ceiling >= monthly_credit_grant", name="valid_rollover_ceiling"),
        CheckConstraint("char_length(currency) = 3", name="currency_iso_length"),
        CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name="valid_effective_dates",
        ),
        UniqueConstraint("public_reference", "effective_from"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_credit_grant: Mapped[int] = mapped_column(Integer, nullable=False)
    rollover_ceiling: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_through: Mapped[date | None] = mapped_column(Date)


class Membership(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'cancelled', 'expired')", name="valid_status"
        ),
        CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="valid_membership_dates"),
        CheckConstraint("terms_version > 0", name="positive_terms_version"),
        Index(
            "uq_memberships_customer_current",
            "customer_id",
            unique=True,
            postgresql_where=text("status IN ('active', 'paused')"),
        ),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("business.customers.id"), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.membership_plans.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    starts_at: Mapped[date] = mapped_column(Date, nullable=False)
    ends_at: Mapped[date | None] = mapped_column(Date)
    next_renewal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_policy_id: Mapped[str] = mapped_column(String(32), nullable=False, default="POL-MEM")
    terms_version: Mapped[int] = mapped_column(Integer, nullable=False)


class MembershipLedgerEntry(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "membership_ledger"
    __table_args__ = (
        CheckConstraint("credit_delta <> 0", name="nonzero_credit_delta"),
        CheckConstraint(
            "entry_type IN ('grant', 'consume', 'expire', 'correction', 'reversal')",
            name="valid_entry_type",
        ),
        CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'external_provider')",
            name="valid_actor_type",
        ),
        CheckConstraint(
            "(entry_type = 'grant' AND credit_delta > 0) OR entry_type <> 'grant'",
            name="grant_is_positive",
        ),
        CheckConstraint(
            "(entry_type IN ('consume', 'expire') AND credit_delta < 0) "
            "OR entry_type NOT IN ('consume', 'expire')",
            name="consumption_and_expiry_negative",
        ),
        Index("ix_membership_ledger_membership_effective", "membership_id", "effective_at", "id"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.memberships.id", ondelete="CASCADE"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    credit_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    related_appointment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business.appointments.id")
    )
    related_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business.membership_ledger.id")
    )
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_reference: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)


class MembershipCreditAllocation(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "membership_credit_allocations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        UniqueConstraint("consumption_entry_id", "grant_entry_id"),
        {"schema": "business"},
    )

    consumption_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.membership_ledger.id", ondelete="CASCADE"), nullable=False
    )
    grant_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("business.membership_ledger.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
