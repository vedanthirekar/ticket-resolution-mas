"""remove case priority

Revision ID: 20260905_0010
Revises: 20260904_0009
Create Date: 2026-09-05
"""

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0010"
down_revision: str | None = "20260904_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rewrite_fingerprints(*, include_priority: bool) -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, claimed_customer_reference, claimed_category, complaint_text, "
            "source, priority FROM case_management.cases"
        )
    ).mappings()
    update = sa.text(
        "UPDATE case_management.cases SET request_fingerprint = :fingerprint WHERE id = :case_id"
    )
    for row in rows:
        payload: dict[str, Any] = {
            "claimed_customer_reference": row["claimed_customer_reference"],
            "claimed_category": row["claimed_category"],
            "complaint_text": row["complaint_text"],
            "source": row["source"],
        }
        if include_priority:
            payload["priority"] = row["priority"]
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        connection.execute(update, {"fingerprint": fingerprint, "case_id": row["id"]})


def upgrade() -> None:
    _rewrite_fingerprints(include_priority=False)
    op.drop_constraint(
        op.f("ck_cases_valid_priority"),
        "cases",
        schema="case_management",
        type_="check",
    )
    op.drop_column("cases", "priority", schema="case_management")


def downgrade() -> None:
    op.add_column(
        "cases",
        sa.Column(
            "priority",
            sa.String(length=16),
            nullable=False,
            server_default="normal",
        ),
        schema="case_management",
    )
    op.create_check_constraint(
        op.f("ck_cases_valid_priority"),
        "cases",
        "priority IN ('normal', 'high', 'urgent')",
        schema="case_management",
    )
    _rewrite_fingerprints(include_priority=True)
    op.alter_column(
        "cases",
        "priority",
        server_default=None,
        schema="case_management",
    )
