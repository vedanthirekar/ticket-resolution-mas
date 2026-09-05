"""widen evidence source references

Revision ID: 20260904_0009
Revises: 20260904_0008
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0009"
down_revision: str | None = "20260904_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "evidence_items",
        "source_reference",
        existing_type=sa.String(length=128),
        type_=sa.Text(),
        existing_nullable=True,
        schema="ai_runtime",
    )


def downgrade() -> None:
    op.alter_column(
        "evidence_items",
        "source_reference",
        existing_type=sa.Text(),
        type_=sa.String(length=128),
        existing_nullable=True,
        schema="ai_runtime",
    )
