from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from time import perf_counter
from typing import Any

from luma.config import get_settings
from luma.db.session import Database
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.retrieval.indexing import index_policy_sections
from luma.retrieval.policy import search_policy
from luma.runtime import configure_asyncio_policy
from luma.tools.contracts import PolicySearchInput

DATASET_PATH = Path("evals/datasets/policy_retrieval_v1.json")
DATASET: dict[str, Any] = json.loads(DATASET_PATH.read_text(encoding="utf-8"))


async def evaluate() -> dict[str, Any]:
    dataset = DATASET
    cases: list[dict[str, Any]] = dataset["cases"]
    provider = HashingEmbeddingProvider()
    settings = get_settings()
    database = Database(settings.database_url, echo=settings.database_echo)
    details: list[dict[str, Any]] = []
    latencies: list[float] = []
    try:
        async with database.transaction() as session:
            indexed_count = await index_policy_sections(session, provider)
        async with database.session() as session:
            for evaluation in cases:
                started = perf_counter()
                result = await search_policy(
                    session,
                    PolicySearchInput(
                        query=evaluation["query"],
                        effective_on=date.fromisoformat(evaluation["effective_on"]),
                        policy_id=evaluation["policy_id"],
                        limit=10,
                    ),
                    provider,
                )
                latency_ms = (perf_counter() - started) * 1000
                latencies.append(latency_ms)
                expected = set(evaluation["expected_section_ids"])
                hybrid_top_five = {hit.section_id for hit in result.data[:5]}
                lexical_top_five = {
                    hit.section_id
                    for hit in result.data
                    if hit.lexical_rank is not None and hit.lexical_rank <= 5
                }
                vector_top_five = {
                    hit.section_id
                    for hit in result.data
                    if hit.vector_rank is not None and hit.vector_rank <= 5
                }
                details.append(
                    {
                        "id": evaluation["id"],
                        "hybrid_hit_at_5": bool(expected & hybrid_top_five),
                        "lexical_hit_at_5": bool(expected & lexical_top_five),
                        "vector_hit_at_5": bool(expected & vector_top_five),
                        "top_5": [hit.section_id for hit in result.data[:5]],
                        "latency_ms": round(latency_ms, 2),
                    }
                )
    finally:
        await database.dispose()

    def recall(metric: str) -> float:
        return sum(bool(item[metric]) for item in details) / len(details)

    ordered_latency = sorted(latencies)
    p95_index = min(len(ordered_latency) - 1, int(len(ordered_latency) * 0.95))
    return {
        "dataset_version": dataset["dataset_version"],
        "embedding_provider": provider.model_name,
        "indexed_sections": indexed_count,
        "case_count": len(details),
        "hybrid_recall_at_5": round(recall("hybrid_hit_at_5"), 4),
        "lexical_recall_at_5": round(recall("lexical_hit_at_5"), 4),
        "vector_recall_at_5": round(recall("vector_hit_at_5"), 4),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 2),
        "p95_latency_ms": round(ordered_latency[p95_index], 2),
        "details": details,
    }


def main() -> None:
    configure_asyncio_policy()
    print(json.dumps(asyncio.run(evaluate()), indent=2))


if __name__ == "__main__":
    main()
