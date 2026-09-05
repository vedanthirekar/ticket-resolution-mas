from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from luma.db.base import Base
from luma.db.models.common import TimestampMixin, UuidPrimaryKeyMixin


class PolicyDocument(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "policy_documents"
    __table_args__ = ({"schema": "knowledge"},)

    policy_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    policy_area: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class PolicyVersion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint(
            "effective_through IS NULL OR effective_through >= effective_from",
            name="valid_effective_dates",
        ),
        CheckConstraint("status IN ('draft', 'active', 'superseded')", name="valid_status"),
        UniqueConstraint("policy_document_id", "version"),
        {"schema": "knowledge"},
    )

    policy_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge.policy_documents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_through: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    supersedes_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge.policy_versions.id")
    )
    source_path: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PolicySection(UuidPrimaryKeyMixin, Base):
    __tablename__ = "policy_sections"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        UniqueConstraint("policy_version_id", "section_id"),
        Index("ix_policy_sections_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_policy_sections_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"schema": "knowledge"},
    )

    policy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge.policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    parent_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge.policy_sections.id")
    )
    heading: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(768))
    embedding_model: Mapped[str | None] = mapped_column(String(96))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(heading, '') || ' ' || coalesce(body, ''))",
            persisted=True,
        ),
    )


class PolicySectionLink(UuidPrimaryKeyMixin, Base):
    __tablename__ = "policy_section_links"
    __table_args__ = (
        CheckConstraint(
            "link_type IN ('references', 'exception_to', 'supersedes', 'related')",
            name="valid_link_type",
        ),
        CheckConstraint("source_section_id <> target_section_id", name="different_sections"),
        UniqueConstraint("source_section_id", "target_section_id", "link_type"),
        {"schema": "knowledge"},
    )

    source_section_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge.policy_sections.id", ondelete="CASCADE"), nullable=False
    )
    target_section_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge.policy_sections.id", ondelete="CASCADE"), nullable=False
    )
    link_type: Mapped[str] = mapped_column(String(24), nullable=False)
