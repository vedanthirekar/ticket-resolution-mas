from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.knowledge import PolicyDocument, PolicySection, PolicyVersion
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.retrieval.indexing import index_policy_sections
from luma.retrieval.policy import fetch_policy_section, search_policy
from luma.tools.contracts import PolicySearchInput, PolicySectionFetchInput
from luma.tools.errors import EntityNotFoundError

pytestmark = pytest.mark.integration
DATASET_PATH = Path("evals/datasets/policy_retrieval_v1.json")


def _dataset() -> list[dict[str, Any]]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))["cases"]


async def test_policy_retrieval_recall_at_five_and_temporal_precision(database) -> None:
    provider = HashingEmbeddingProvider()
    async with database.transaction() as session:
        await index_policy_sections(session, provider)

    successes = 0
    async with database.session() as session:
        for evaluation in _dataset():
            result = await search_policy(
                session,
                PolicySearchInput(
                    query=evaluation["query"],
                    effective_on=date.fromisoformat(evaluation["effective_on"]),
                    policy_id=evaluation["policy_id"],
                    limit=5,
                ),
                provider,
            )
            returned = {hit.section_id for hit in result.data}
            if returned.intersection(evaluation["expected_section_ids"]):
                successes += 1
            assert all(
                hit.effective_from <= date.fromisoformat(evaluation["effective_on"])
                and (
                    hit.effective_through is None
                    or hit.effective_through >= date.fromisoformat(evaluation["effective_on"])
                )
                for hit in result.data
            )

    recall_at_five = successes / len(_dataset())
    assert recall_at_five >= 0.90


async def test_policy_version_boundary_never_returns_temporally_invalid_version(database) -> None:
    provider = HashingEmbeddingProvider()
    async with database.session() as session:
        old = await search_policy(
            session,
            PolicySearchInput(
                query="standard cancellation notice window",
                effective_on=date(2025, 6, 30),
                policy_id="POL-CAN",
            ),
            provider,
        )
        new = await search_policy(
            session,
            PolicySearchInput(
                query="standard cancellation notice window",
                effective_on=date(2025, 7, 1),
                policy_id="POL-CAN",
            ),
            provider,
        )

    assert old.data and {hit.version for hit in old.data} == {1}
    assert new.data and {hit.version for hit in new.data} == {2}


async def test_fetch_policy_section_expands_parent_and_links(database) -> None:
    async with database.session() as session:
        result = await fetch_policy_section(
            session,
            PolicySectionFetchInput(section_id="POL-CAN-v2#4.2", effective_on=date(2026, 8, 1)),
        )

    assert result.data.section.section_id == "POL-CAN-v2#4.2"
    assert result.data.parent is not None
    assert result.data.parent.section_id == "POL-CAN-v2#4"
    assert result.data.section.provenance.source_table == "knowledge.policy_sections"


async def test_fetch_rejects_section_outside_effective_version(database) -> None:
    async with database.session() as session:
        with pytest.raises(EntityNotFoundError):
            await fetch_policy_section(
                session,
                PolicySectionFetchInput(
                    section_id="POL-CAN-v2#3.1", effective_on=date(2025, 6, 30)
                ),
            )


async def test_location_scope_is_a_hard_filter_before_ranking(database) -> None:
    provider = HashingEmbeddingProvider()
    async with database.engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            document = PolicyDocument(
                policy_id="POL-SCOPE-TEST",
                title="Scoped Test Policy",
                policy_area="testing",
            )
            session.add(document)
            await session.flush()
            version = PolicyVersion(
                policy_document_id=document.id,
                version=1,
                effective_from=date(2026, 1, 1),
                status="active",
                scope={"location_references": ["LOC-IND"]},
                source_path="test/POL-SCOPE-TEST-v1.md",
                content_checksum="c" * 64,
            )
            session.add(version)
            await session.flush()
            session.add(
                PolicySection(
                    policy_version_id=version.id,
                    section_id="POL-SCOPE-TEST-v1#1",
                    heading="Only Indianapolis",
                    body="This unique policy applies only in Indianapolis.",
                    sort_order=1,
                    content_checksum="d" * 64,
                )
            )
            await session.flush()
            await index_policy_sections(session, provider)

            allowed = await search_policy(
                session,
                PolicySearchInput(
                    query="unique Indianapolis policy",
                    effective_on=date(2026, 8, 1),
                    policy_id="POL-SCOPE-TEST",
                    location_reference="LOC-IND",
                ),
                provider,
            )
            excluded = await search_policy(
                session,
                PolicySearchInput(
                    query="unique Indianapolis policy",
                    effective_on=date(2026, 8, 1),
                    policy_id="POL-SCOPE-TEST",
                    location_reference="LOC-CHI",
                ),
                provider,
            )
            assert [hit.section_id for hit in allowed.data] == ["POL-SCOPE-TEST-v1#1"]
            assert excluded.data == []
        await transaction.rollback()
