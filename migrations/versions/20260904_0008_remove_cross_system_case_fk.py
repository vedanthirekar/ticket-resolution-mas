"""remove cross-system case-to-customer foreign key

Revision ID: 20260904_0008
Revises: 20260904_0007
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260904_0008"
down_revision: str | None = "20260904_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_cases_customer_id_customers",
        "cases",
        schema="case_management",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "fk_cases_customer_id_customers",
        "cases",
        "customers",
        ["customer_id"],
        ["id"],
        source_schema="case_management",
        referent_schema="business",
    )
