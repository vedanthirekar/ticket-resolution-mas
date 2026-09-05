from __future__ import annotations

import pytest
from luma_enterprise.config import GenerationConfig
from luma_enterprise.generator import generate_dataset
from sqlalchemy import delete, select

from luma.db.models.case_management import SupportCase
from luma.db.session import Database
from luma.domain.cases import CaseSource
from luma.services.cases import CreateCaseCommand, create_case

pytestmark = [pytest.mark.data_integrity, pytest.mark.integration]


async def test_dataset_rebuild_is_logically_reproducible(database: Database) -> None:
    config = GenerationConfig()
    request_key = "enterprise-boundary-test"
    async with database.transaction() as session:
        await session.execute(
            delete(SupportCase).where(SupportCase.external_request_key == request_key)
        )
        marker = await create_case(
            session,
            CreateCaseCommand(
                complaint_text="A product-owned case must survive source-data maintenance.",
                source=CaseSource.API,
                external_request_key=request_key,
            ),
        )
    try:
        with pytest.raises(RuntimeError, match="application cases exist"):
            await generate_dataset(database, config, write_manifests=False)
        first_manifest, first_report = await generate_dataset(
            database, config, write_manifests=False, allow_runtime_data=True
        )
        second_manifest, second_report = await generate_dataset(
            database, config, write_manifests=False, allow_runtime_data=True
        )
        async with database.session() as session:
            assert await session.scalar(
                select(SupportCase.id).where(SupportCase.id == marker.case.id)
            )
    finally:
        async with database.transaction() as session:
            await session.execute(
                delete(SupportCase).where(SupportCase.external_request_key == request_key)
            )

    assert first_report.passed
    assert second_report.passed
    assert first_manifest["row_counts"] == second_manifest["row_counts"]
    assert first_manifest["checksums"] == second_manifest["checksums"]
    assert first_manifest["dataset_fingerprint"] == second_manifest["dataset_fingerprint"]
    assert (
        first_manifest["canonical_record_references"]
        == second_manifest["canonical_record_references"]
    )
