from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import insert, text

from luma.db.base import Base
from luma.db.models import ALL_MODELS
from luma.db.session import Database
from luma_enterprise.builder import build_operational_rows
from luma_enterprise.config import GenerationConfig
from luma_enterprise.policies import build_policy_rows
from luma_enterprise.validation import ValidationReport, dataset_fingerprint, validate_dataset

ENTERPRISE_ROOT = Path(__file__).resolve().parents[1]

assert ALL_MODELS

TABLE_NAMES = (
    "business.locations",
    "business.location_business_hours",
    "business.employees",
    "business.employee_locations",
    "business.services",
    "business.location_services",
    "business.employee_services",
    "business.employee_schedules",
    "business.customers",
    "business.appointments",
    "business.appointment_events",
    "business.invoices",
    "business.invoice_items",
    "business.payments",
    "business.payment_events",
    "business.refunds",
    "business.membership_plans",
    "business.memberships",
    "business.membership_ledger",
    "business.membership_credit_allocations",
    "business.booking_settings",
    "business.location_service_settings",
    "business.employee_booking_settings",
    "business.location_resources",
    "business.booking_blocks",
    "business.booking_attempts",
    "business.audit_events",
    "knowledge.policy_documents",
    "knowledge.policy_versions",
    "knowledge.policy_sections",
    "knowledge.policy_section_links",
)
TABLE_ORDER = tuple(Base.metadata.tables[name] for name in TABLE_NAMES)


async def _replace_rows(database: Database, rows: dict[str, list[dict[str, Any]]]) -> None:
    qualified_tables = ", ".join(
        f'"{table.schema}"."{table.name}"' for table in reversed(TABLE_ORDER)
    )
    async with database.transaction() as session:
        await session.execute(text(f"TRUNCATE TABLE {qualified_tables} CASCADE"))
        for table in TABLE_ORDER:
            table_rows = rows.get(table.name, [])
            if table_rows:
                await session.execute(insert(table), table_rows)


async def _assert_no_runtime_cases(database: Database) -> None:
    async with database.session() as session:
        count = int(await session.scalar(text("SELECT count(*) FROM case_management.cases")) or 0)
    if count:
        raise RuntimeError(
            "refusing to replace enterprise source data while application cases exist; "
            "use the explicit force option only in an isolated test/demo reset"
        )


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def generate_dataset(
    database: Database,
    config: GenerationConfig | None = None,
    *,
    write_manifests: bool = True,
    allow_runtime_data: bool = False,
) -> tuple[dict[str, Any], ValidationReport]:
    active_config = config or GenerationConfig()
    if not allow_runtime_data:
        await _assert_no_runtime_cases(database)
    rows, incident_references = build_operational_rows(active_config)

    policy_rows = build_policy_rows(
        dataset_version=active_config.dataset_version,
        policy_directory=ENTERPRISE_ROOT / "business_spec" / "policies",
        generated_at=active_config.reference_time,
    )
    rows.update(
        {
            "policy_documents": policy_rows.documents,
            "policy_versions": policy_rows.versions,
            "policy_sections": policy_rows.sections,
            "policy_section_links": policy_rows.links,
        }
    )
    await _replace_rows(database, rows)

    async with database.session() as session:
        revision = str(
            (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        )
        report = await validate_dataset(session)
    if not report.passed:
        raise RuntimeError(f"Generated dataset failed validation: {report.summary()}")

    manifest = {
        "dataset_version": active_config.dataset_version,
        "generator_version": active_config.generator_version,
        "seed": active_config.seed,
        "reference_time": active_config.reference_time.isoformat().replace("+00:00", "Z"),
        "alembic_revision": revision,
        "row_counts": report.row_counts,
        "canonical_record_references": incident_references,
        "validation_summary": report.summary(),
        "checksums": report.checksums,
        "dataset_fingerprint": dataset_fingerprint(report.checksums),
        "distribution_config": {
            "customers": active_config.customer_count,
            "memberships": active_config.membership_count,
            "appointments": active_config.appointment_count,
            "background_payments": active_config.background_payment_count,
        },
        "checksum_exclusions": ["created_at", "updated_at", "recorded_at"],
    }
    incident_manifest = {
        "dataset_version": active_config.dataset_version,
        "deployment": "build-time only; never packaged with the runtime service",
        "canonical_incidents": incident_references,
        "expected_anomalies": list(report.expected_anomalies),
    }
    if write_manifests:
        _write_json(ENTERPRISE_ROOT / active_config.manifest_path, manifest)
        _write_json(ENTERPRISE_ROOT / active_config.incident_manifest_path, incident_manifest)
    return manifest, report
