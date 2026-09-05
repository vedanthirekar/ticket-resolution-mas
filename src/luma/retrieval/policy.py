from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import Select, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.knowledge import (
    PolicyDocument,
    PolicySection,
    PolicySectionLink,
    PolicyVersion,
)
from luma.retrieval.embeddings import EmbeddingProvider
from luma.tools.contracts import (
    PolicySearchHit,
    PolicySearchInput,
    PolicySectionDetail,
    PolicySectionFetchInput,
    Provenance,
    ToolMetadata,
    ToolResult,
)
from luma.tools.errors import EntityNotFoundError

RRF_K = 60
LEXICAL_WEIGHT = 1.5
VECTOR_WEIGHT = 1.0
LEXICAL_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
LEXICAL_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "be",
        "but",
        "do",
        "does",
        "for",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "should",
        "the",
        "to",
        "was",
        "were",
        "when",
        "with",
    }
)


@dataclass(frozen=True, slots=True)
class _PolicyRow:
    section_id: UUID
    public_section_id: str
    parent_section_id: UUID | None
    heading: str
    body: str
    policy_id: str
    policy_title: str
    policy_area: str
    version: int
    effective_from: date
    effective_through: date | None


def _metadata(tool_name: str, count: int) -> ToolMetadata:
    return ToolMetadata(
        tool_call_id=f"TOOL-{uuid4().hex}",
        tool_name=tool_name,
        executed_at=datetime.now(UTC),
        result_count=count,
    )


def _base_query(
    *,
    effective_on: date,
    policy_id: str | None = None,
    policy_area: str | None = None,
    location_reference: str | None = None,
    service_reference: str | None = None,
) -> Select[tuple[UUID, str, UUID | None, str, str, str, str, str, int, date, date | None]]:
    statement = (
        select(
            PolicySection.id,
            PolicySection.section_id,
            PolicySection.parent_section_id,
            PolicySection.heading,
            PolicySection.body,
            PolicyDocument.policy_id,
            PolicyDocument.title,
            PolicyDocument.policy_area,
            PolicyVersion.version,
            PolicyVersion.effective_from,
            PolicyVersion.effective_through,
        )
        .join(PolicyVersion, PolicyVersion.id == PolicySection.policy_version_id)
        .join(PolicyDocument, PolicyDocument.id == PolicyVersion.policy_document_id)
        .where(
            PolicyVersion.status.in_(["active", "superseded"]),
            PolicyVersion.effective_from <= effective_on,
            or_(
                PolicyVersion.effective_through.is_(None),
                PolicyVersion.effective_through >= effective_on,
            ),
        )
    )
    if policy_id:
        statement = statement.where(PolicyDocument.policy_id == policy_id)
    if policy_area:
        statement = statement.where(PolicyDocument.policy_area == policy_area)
    if location_reference:
        has_locations = PolicyVersion.scope.op("?")("location_references")
        statement = statement.where(
            or_(
                not_(has_locations),
                PolicyVersion.scope["location_references"].contains([location_reference]),
                PolicyVersion.scope["location_references"].contains(["all"]),
            )
        )
    if service_reference:
        has_services = PolicyVersion.scope.op("?")("service_references")
        statement = statement.where(
            or_(
                not_(has_services),
                PolicyVersion.scope["service_references"].contains([service_reference]),
                PolicyVersion.scope["service_references"].contains(["all"]),
            )
        )
    return statement


def _to_policy_row(row: object) -> _PolicyRow:
    values: tuple[Any, ...] = tuple(cast(Any, row))
    return _PolicyRow(
        section_id=cast(UUID, values[0]),
        public_section_id=cast(str, values[1]),
        parent_section_id=cast(UUID | None, values[2]),
        heading=cast(str, values[3]),
        body=cast(str, values[4]),
        policy_id=cast(str, values[5]),
        policy_title=cast(str, values[6]),
        policy_area=cast(str, values[7]),
        version=cast(int, values[8]),
        effective_from=cast(date, values[9]),
        effective_through=cast(date | None, values[10]),
    )


def _hit(
    row: _PolicyRow,
    *,
    lexical_rank: int | None,
    vector_rank: int | None,
    score: float,
) -> PolicySearchHit:
    return PolicySearchHit(
        section_id=row.public_section_id,
        policy_id=row.policy_id,
        policy_title=row.policy_title,
        policy_area=row.policy_area,
        version=row.version,
        effective_from=row.effective_from,
        effective_through=row.effective_through,
        heading=row.heading,
        body=row.body,
        lexical_rank=lexical_rank,
        vector_rank=vector_rank,
        rrf_score=score,
        provenance=Provenance(
            source_table="knowledge.policy_sections",
            source_reference=row.public_section_id,
        ),
    )


async def search_policy(
    session: AsyncSession,
    request: PolicySearchInput,
    provider: EmbeddingProvider,
) -> ToolResult[list[PolicySearchHit]]:
    """Run hard-filtered lexical/vector retrieval and reciprocal-rank fusion."""
    base = _base_query(
        effective_on=request.effective_on,
        policy_id=request.policy_id,
        policy_area=request.policy_area,
        location_reference=request.location_reference,
        service_reference=request.service_reference,
    )
    candidate_limit = max(20, request.limit * 4)
    lexical_tokens = [
        token
        for token in LEXICAL_TOKEN_PATTERN.findall(request.query.lower())
        if token not in LEXICAL_STOPWORDS
    ]
    lexical_query = " OR ".join(lexical_tokens) if lexical_tokens else request.query
    query = func.websearch_to_tsquery("english", lexical_query)
    lexical_score = func.ts_rank_cd(PolicySection.search_vector, query)
    lexical_rows = (
        await session.execute(
            base.where(PolicySection.search_vector.op("@@")(query))
            .order_by(lexical_score.desc(), PolicySection.section_id)
            .limit(candidate_limit)
        )
    ).all()

    query_vector = await provider.embed_query(request.query)
    if len(query_vector) != 768:
        raise ValueError("policy query embedding must contain 768 dimensions")
    distance = PolicySection.embedding.cosine_distance(query_vector)
    vector_rows = (
        await session.execute(
            base.where(
                PolicySection.embedding.is_not(None),
                PolicySection.embedding_model == provider.model_name,
            )
            .order_by(distance, PolicySection.section_id)
            .limit(candidate_limit)
        )
    ).all()

    rows: dict[str, _PolicyRow] = {}
    lexical_ranks: dict[str, int] = {}
    vector_ranks: dict[str, int] = {}
    scores: defaultdict[str, float] = defaultdict(float)
    for rank, raw_row in enumerate(lexical_rows, start=1):
        row = _to_policy_row(raw_row)
        rows[row.public_section_id] = row
        lexical_ranks[row.public_section_id] = rank
        scores[row.public_section_id] += LEXICAL_WEIGHT / (RRF_K + rank)
    for rank, raw_row in enumerate(vector_rows, start=1):
        row = _to_policy_row(raw_row)
        rows[row.public_section_id] = row
        vector_ranks[row.public_section_id] = rank
        scores[row.public_section_id] += VECTOR_WEIGHT / (RRF_K + rank)

    ranked_ids = sorted(scores, key=lambda item: (-scores[item], item))[: request.limit]
    hits = [
        _hit(
            rows[section_id],
            lexical_rank=lexical_ranks.get(section_id),
            vector_rank=vector_ranks.get(section_id),
            score=scores[section_id],
        )
        for section_id in ranked_ids
    ]
    return ToolResult(metadata=_metadata("search_policy", len(hits)), data=hits)


async def _fetch_row(
    session: AsyncSession,
    *,
    section_uuid: UUID | None = None,
    public_section_id: str | None = None,
    request: PolicySectionFetchInput,
) -> _PolicyRow | None:
    statement = _base_query(
        effective_on=request.effective_on,
        location_reference=request.location_reference,
        service_reference=request.service_reference,
    )
    if section_uuid is not None:
        statement = statement.where(PolicySection.id == section_uuid)
    if public_section_id is not None:
        statement = statement.where(PolicySection.section_id == public_section_id)
    row = (await session.execute(statement)).one_or_none()
    return None if row is None else _to_policy_row(row)


async def fetch_policy_section(
    session: AsyncSession, request: PolicySectionFetchInput
) -> ToolResult[PolicySectionDetail]:
    selected = await _fetch_row(session, public_section_id=request.section_id, request=request)
    if selected is None:
        raise EntityNotFoundError("an applicable policy section was not found")
    parent = None
    if selected.parent_section_id:
        parent = await _fetch_row(session, section_uuid=selected.parent_section_id, request=request)

    links = (
        (
            await session.execute(
                select(PolicySectionLink).where(
                    or_(
                        PolicySectionLink.source_section_id == selected.section_id,
                        PolicySectionLink.target_section_id == selected.section_id,
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    linked_rows: list[tuple[_PolicyRow, str]] = []
    for link in links:
        linked_id = (
            link.target_section_id
            if link.source_section_id == selected.section_id
            else link.source_section_id
        )
        linked = await _fetch_row(session, section_uuid=linked_id, request=request)
        if linked is not None:
            linked_rows.append((linked, link.link_type))

    detail = PolicySectionDetail(
        section=_hit(selected, lexical_rank=None, vector_rank=None, score=0.0),
        parent=(_hit(parent, lexical_rank=None, vector_rank=None, score=0.0) if parent else None),
        linked_sections=[
            _hit(row, lexical_rank=None, vector_rank=None, score=0.0) for row, _ in linked_rows
        ],
        link_types={
            row.public_section_id: cast(
                Literal["references", "exception_to", "supersedes", "related"], link_type
            )
            for row, link_type in linked_rows
        },
    )
    return ToolResult(metadata=_metadata("fetch_policy_section", 1 + len(linked_rows)), data=detail)
