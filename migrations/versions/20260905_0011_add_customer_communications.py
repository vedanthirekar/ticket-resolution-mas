"""add customer contact email and final communications

Revision ID: 20260905_0011
Revises: 20260905_0010
Create Date: 2026-09-05
"""

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0011"
down_revision: str | None = "20260905_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rewrite_fingerprints(*, include_contact_email: bool) -> None:
    connection = op.get_bind()
    fields = (
        "id, claimed_customer_reference, contact_email, claimed_category, complaint_text, source"
        if include_contact_email
        else "id, claimed_customer_reference, claimed_category, complaint_text, source"
    )
    rows = connection.execute(sa.text(f"SELECT {fields} FROM case_management.cases")).mappings()
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
        if include_contact_email:
            payload["contact_email"] = row["contact_email"]
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        connection.execute(update, {"fingerprint": fingerprint, "case_id": row["id"]})


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        schema="case_management",
    )
    _rewrite_fingerprints(include_contact_email=True)
    op.create_table(
        "customer_communications",
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("communication_type", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_reference", sa.String(length=64), nullable=True),
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "channel = 'email'", name=op.f("ck_customer_communications_valid_channel")
        ),
        sa.CheckConstraint(
            "status IN ('prepared', 'sent')",
            name=op.f("ck_customer_communications_valid_status"),
        ),
        sa.CheckConstraint(
            "communication_type = 'final_resolution'",
            name=op.f("ck_customer_communications_valid_type"),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["case_management.cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sent_by_account_id"], ["case_management.operations_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "communication_type"),
        sa.UniqueConstraint("delivery_reference"),
        schema="case_management",
    )
    op.create_index(
        "ix_customer_communications_case_status",
        "customer_communications",
        ["case_id", "status"],
        unique=False,
        schema="case_management",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_customer_communications_case_status",
        table_name="customer_communications",
        schema="case_management",
    )
    op.drop_table("customer_communications", schema="case_management")
    _rewrite_fingerprints(include_contact_email=False)
    op.drop_column("cases", "contact_email", schema="case_management")
