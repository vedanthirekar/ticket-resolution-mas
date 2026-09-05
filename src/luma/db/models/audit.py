from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from luma.db.base import Base
from luma.db.models.common import UuidPrimaryKeyMixin


class AuditEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('customer', 'employee', 'system', 'external_provider')",
            name="valid_actor_type",
        ),
        Index("ix_audit_events_target_occurred", "target_type", "target_reference", "occurred_at"),
        {"schema": "business"},
    )

    public_reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    correlation_reference: Mapped[str | None] = mapped_column(String(64), index=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
