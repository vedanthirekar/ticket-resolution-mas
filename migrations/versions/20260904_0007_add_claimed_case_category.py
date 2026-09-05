"""add customer-claimed case category

Revision ID: 20260904_0007
Revises: 20260904_0006
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0007"
down_revision: str | None = "20260904_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("claimed_category", sa.String(length=48), nullable=True),
        schema="case_management",
    )
    op.create_check_constraint(
        "valid_claimed_category",
        "cases",
        "claimed_category IS NULL OR claimed_category IN ("
        "'duplicate_payment', 'cancellation_fee_dispute', 'missing_appointment', "
        "'membership_credits', 'online_booking_unavailable', 'other')",
        schema="case_management",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_cases_valid_claimed_category",
        "cases",
        schema="case_management",
        type_="check",
    )
    op.drop_column("cases", "claimed_category", schema="case_management")
