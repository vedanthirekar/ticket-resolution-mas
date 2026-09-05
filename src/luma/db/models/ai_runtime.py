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
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from luma.db.base import Base
from luma.db.models.common import CreatedAtMixin, UuidPrimaryKeyMixin


class CaseRun(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "case_runs"
    __table_args__ = (
        CheckConstraint("run_number > 0", name="positive_run_number"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'interrupted')",
            name="valid_status",
        ),
        UniqueConstraint("case_id", "run_number"),
        Index("ix_case_runs_case_created", "case_id", "created_at"),
        {"schema": "ai_runtime"},
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_management.cases.id", ondelete="CASCADE"), nullable=False
    )
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    architecture_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(48))
    model_name: Mapped[str | None] = mapped_column(String(96))
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)


class WorkflowStage(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """Idempotent durable boundary between a graph node and application artifacts."""

    __tablename__ = "workflow_stages"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'completed', 'failed')",
            name="valid_status",
        ),
        UniqueConstraint("case_run_id", "stage_name"),
        Index("ix_workflow_stages_run", "case_run_id", "created_at"),
        {"schema": "ai_runtime"},
    )

    case_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_runtime.case_runs.id", ondelete="CASCADE"), nullable=False
    )
    stage_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    output: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)


class InvestigationPlan(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "investigation_plans"
    __table_args__ = (
        CheckConstraint("revision > 0", name="positive_revision"),
        UniqueConstraint("case_run_id", "revision"),
        {"schema": "ai_runtime"},
    )

    case_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_runtime.case_runs.id", ondelete="CASCADE"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class EvidenceItem(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        CheckConstraint(
            "condition IN ('present', 'known_absent', 'missing', 'unknown', "
            "'contradictory', 'unavailable', 'not_applicable')",
            name="valid_condition",
        ),
        Index("ix_evidence_items_run_type", "case_run_id", "evidence_type"),
        {"schema": "ai_runtime"},
    )

    case_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_runtime.case_runs.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    condition: Mapped[str] = mapped_column(String(24), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    # A single evidence result can carry many authoritative record references.
    # They are serialized as a comma-separated value for the current API.
    source_reference: Mapped[str | None] = mapped_column(Text)
    tool_call_reference: Mapped[str | None] = mapped_column(String(128))
    observed_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PolicyRetrieval(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "policy_retrievals"
    __table_args__ = (Index("ix_policy_retrievals_run", "case_run_id"), {"schema": "ai_runtime"})

    case_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_runtime.case_runs.id", ondelete="CASCADE"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    retrieval_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ranked_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    selected_section_ids: Mapped[list[str]] = mapped_column(ARRAY(String(160)), nullable=False)


class ResolutionProposal(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "resolution_proposals"
    __table_args__ = (
        CheckConstraint(
            "disposition IN ('auto_resolve', 'human_approval', 'human_investigation')",
            name="valid_disposition",
        ),
        UniqueConstraint("case_run_id"),
        {"schema": "ai_runtime"},
    )

    case_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_runtime.case_runs.id", ondelete="CASCADE"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    action_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    evidence_references: Mapped[list[str]] = mapped_column(ARRAY(String(160)), nullable=False)
    policy_references: Mapped[list[str]] = mapped_column(ARRAY(String(160)), nullable=False)


class VerificationResult(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "verification_results"
    __table_args__ = (UniqueConstraint("case_run_id"), {"schema": "ai_runtime"})

    case_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_runtime.case_runs.id", ondelete="CASCADE"), nullable=False
    )
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False)
    missing_evidence: Mapped[list[str]] = mapped_column(ARRAY(String(160)), nullable=False)
    contradictions: Mapped[list[str]] = mapped_column(ARRAY(String(160)), nullable=False)
    unsupported_claims: Mapped[list[str]] = mapped_column(ARRAY(String(160)), nullable=False)
    recommended_outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    recommended_disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    requires_human: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
