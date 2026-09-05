"""add workflow stage idempotency records

Revision ID: 20260904_0005
Revises: 20260903_0004
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260904_0005"
down_revision: str | None = "20260903_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_stages",
        sa.Column("case_run_id", sa.UUID(), nullable=False),
        sa.Column("stage_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed')", name="ck_workflow_stages_valid_status"
        ),
        sa.ForeignKeyConstraint(["case_run_id"], ["ai_runtime.case_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_run_id", "stage_name"),
        schema="ai_runtime",
    )
    op.create_index(
        "ix_workflow_stages_run",
        "workflow_stages",
        ["case_run_id", "created_at"],
        unique=False,
        schema="ai_runtime",
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_stages_run", table_name="workflow_stages", schema="ai_runtime")
    op.drop_table("workflow_stages", schema="ai_runtime")
