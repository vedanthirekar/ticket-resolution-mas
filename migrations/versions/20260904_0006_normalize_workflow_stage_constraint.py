"""normalize workflow stage constraint name

Revision ID: 20260904_0006
Revises: 20260904_0005
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260904_0006"
down_revision: str | None = "20260904_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ai_runtime.workflow_stages "
        "RENAME CONSTRAINT ck_workflow_stages_ck_workflow_stages_valid_status "
        "TO ck_workflow_stages_valid_status"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE ai_runtime.workflow_stages "
        "RENAME CONSTRAINT ck_workflow_stages_valid_status "
        "TO ck_workflow_stages_ck_workflow_stages_valid_status"
    )
