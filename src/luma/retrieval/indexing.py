from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.knowledge import PolicySection
from luma.retrieval.embeddings import EmbeddingProvider


async def index_policy_sections(
    session: AsyncSession, provider: EmbeddingProvider, *, batch_size: int = 32
) -> int:
    """Embed missing/stale sections and stamp the exact provider identity."""
    if provider.dimensions != 768:
        raise ValueError("the current policy embedding column requires 768 dimensions")
    sections = (
        (
            await session.execute(
                select(PolicySection)
                .where(
                    or_(
                        PolicySection.embedding.is_(None),
                        PolicySection.embedding_model != provider.model_name,
                    )
                )
                .order_by(PolicySection.section_id)
            )
        )
        .scalars()
        .all()
    )
    indexed_at = datetime.now(UTC)
    for offset in range(0, len(sections), batch_size):
        batch = sections[offset : offset + batch_size]
        vectors = await provider.embed_documents(
            [f"{section.heading}\n{section.body}" for section in batch]
        )
        if len(vectors) != len(batch):
            raise ValueError("embedding provider returned the wrong batch size")
        for section, vector in zip(batch, vectors, strict=True):
            if len(vector) != provider.dimensions:
                raise ValueError("embedding provider returned the wrong dimensions")
            section.embedding = vector
            section.embedding_model = provider.model_name
            section.embedded_at = indexed_at
        await session.flush()
    return len(sections)
