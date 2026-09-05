from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from luma.db.base import Base
from luma.db.models.common import CreatedAtMixin, TimestampMixin, UuidPrimaryKeyMixin


class OperationsAccount(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operations_accounts"
    __table_args__ = ({"schema": "case_management"},)

    username: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OperationsSession(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "operations_sessions"
    __table_args__ = (
        Index("ix_operations_sessions_token", "token_hash", unique=True),
        Index("ix_operations_sessions_expiry", "expires_at"),
        {"schema": "case_management"},
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.operations_accounts.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportCase(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("source IN ('manual', 'simulator', 'api')", name="valid_source"),
        CheckConstraint(
            "claimed_category IS NULL OR claimed_category IN ("
            "'duplicate_payment', 'cancellation_fee_dispute', 'missing_appointment', "
            "'membership_credits', 'online_booking_unavailable', 'other')",
            name="valid_claimed_category",
        ),
        CheckConstraint("priority IN ('normal', 'high', 'urgent')", name="valid_priority"),
        CheckConstraint(
            "status IN ('received', 'queued', 'processing', 'pending_approval', "
            "'resolved', 'human_investigation', 'failed')",
            name="valid_status",
        ),
        CheckConstraint("char_length(btrim(complaint_text)) > 0", name="nonempty_complaint"),
        CheckConstraint("version > 0", name="positive_version"),
        UniqueConstraint("source", "external_request_key"),
        Index("ix_cases_status_received", "status", "received_at"),
        Index("ix_cases_customer_received", "customer_id", "received_at"),
        {"schema": "case_management"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    external_request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    # Snapshot linkage only. Cross-system foreign keys would let source maintenance
    # cascade into product-owned case history.
    customer_id: Mapped[UUID | None] = mapped_column()
    claimed_customer_reference: Mapped[str | None] = mapped_column(String(32))
    claimed_category: Mapped[str | None] = mapped_column(String(48))
    complaint_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class CaseEvent(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "case_events"
    __table_args__ = (
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'agent')",
            name="valid_actor_type",
        ),
        UniqueConstraint("case_id", "sequence"),
        Index("ix_case_events_case_occurred", "case_id", "occurred_at", "sequence"),
        {"schema": "case_management"},
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.cases.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


class ProcessingJob(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'leased', 'retry_wait', 'succeeded', 'dead_letter', 'cancelled')",
            name="valid_status",
        ),
        CheckConstraint("attempt_count >= 0", name="nonnegative_attempt_count"),
        CheckConstraint("max_attempts > 0", name="positive_max_attempts"),
        CheckConstraint(
            "(status = 'leased' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'leased')",
            name="leased_fields_present",
        ),
        UniqueConstraint("case_id", "job_type"),
        Index("ix_processing_jobs_claim", "status", "available_at", "created_at"),
        Index("ix_processing_jobs_lease_expiry", "lease_expires_at"),
        {"schema": "case_management"},
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.cases.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, default="case_resolution")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_detail: Mapped[str | None] = mapped_column(Text)


class ActionIntent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "action_intents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'pending_approval', 'approved', 'rejected', "
            "'executing', 'succeeded', 'failed', 'cancelled')",
            name="valid_status",
        ),
        Index("ix_action_intents_case_status", "case_id", "status"),
        {"schema": "case_management"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.cases.id", ondelete="CASCADE"), nullable=False
    )
    case_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_runtime.case_runs.id", ondelete="SET NULL")
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)


class Approval(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected')", name="valid_decision"),
        UniqueConstraint("action_intent_id"),
        {"schema": "case_management"},
    )

    action_intent_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.action_intents.id", ondelete="CASCADE"), nullable=False
    )
    decided_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.operations_accounts.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ExecutionAttempt(UuidPrimaryKeyMixin, Base):
    __tablename__ = "execution_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="positive_attempt_number"),
        CheckConstraint(
            "status IN ('started', 'succeeded', 'failed', 'indeterminate')",
            name="valid_status",
        ),
        UniqueConstraint("action_intent_id", "attempt_number"),
        {"schema": "case_management"},
    )

    action_intent_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.action_intents.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    executor: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="started")
    external_reference: Mapped[str | None] = mapped_column(String(128))
    response_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Escalation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "escalations"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'acknowledged', 'resolved')", name="valid_status"),
        Index("ix_escalations_status_created", "status", "created_at"),
        {"schema": "case_management"},
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.cases.id", ondelete="CASCADE"), nullable=False
    )
    case_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_runtime.case_runs.id", ondelete="SET NULL")
    )
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    resolved_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("case_management.operations_accounts.id")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
