# Gate D Deterministic Evidence Review

Status: **Approved on September 4, 2026**

M6 multi-agent orchestration must not begin until the deterministic tools and
policy retrieval contract below are accepted or revised.

## Delivered evidence

| Requirement | Result |
|---|---|
| Exact operational lookup | Canonical customer, appointment, payment, membership, and booking records return expected authoritative values |
| Ownership isolation | Cross-customer appointment lookup returns safe not-found; no record content is disclosed |
| Bounded output | List inputs cap at 50 and report truncation; ledger input caps at 200 and refuses an incomplete oversized slice |
| Provenance | Every result has a tool-call ID and every returned record names its source table/reference |
| Booking diagnosis | Canonical employee override, missing qualification, schedule gap, and closed-location facts are independently exposed |
| Temporal policy filtering | June 30, 2025 returns only cancellation policy v1; July 1 returns only v2 |
| Scope filtering | A transaction-isolated location-scoped policy is retrievable for `LOC-IND` and absent for `LOC-CHI` before ranking |
| Section expansion | Fetch returns selected section, logical parent, and applicable linked sections |
| Retrieval recall@5 | 16/17 = **94.12%**, threshold >= 90% |
| Invalid temporal/scope results | **0** |
| External model calls | **0** |

Representative local evaluation run using PostgreSQL in Docker:

- Dataset: `policy_retrieval_v1`, 17 cases
- Embedding baseline: `luma-feature-hash-768-v1`
- Hybrid recall@5: 94.12%
- Lexical recall@5: 94.12%
- Vector-baseline recall@5: 94.12%
- Mean retrieval latency: 10.98 ms
- P95 retrieval latency: 25.54 ms

Latency is a local development observation, not a production service-level claim.

## Verification evidence

- Alembic revision `20260903_0004` adds nullable model-stamped embeddings and the
  HNSW cosine index without changing frozen policy content.
- 35 tests pass across business integrity, schema parity, durable runtime,
  operational tools, policy retrieval, authentication, and safety behavior.
- Ruff formatting/lint and strict mypy pass.
- `evals/run_policy_retrieval.py` prints per-case top-five results and channel
  metrics, keeping the missed query visible.

## Review decisions

| Decision | Proposed choice | Review status |
|---|---|---|
| Operational access | Typed, customer-scoped tools only; no arbitrary SQL | Approved |
| Discovery | Customer-scoped bounded appointment and booking-attempt lists precede exact detail tools | Approved |
| Evidence semantics | Tools return facts/provenance, not a resolution conclusion | Approved |
| Retrieval | Hard applicability filters -> lexical/vector candidates -> weighted RRF | Approved |
| Temporal safety | Material event date is mandatory for all search/fetch calls | Approved |
| Embedding baseline | Permit M6 with deterministic offline vectors; require real-provider rerun before final quality claims | Approved |
| Known miss | Preserve the 1/17 expiry-query miss for later embedding/prompt analysis | Approved |

Approval authorizes M6 LangGraph orchestration over these contracts. It does not
approve mutation execution, which remains an M7 safety gate.

## Approval record

The project owner approved Gate D in the implementation discussion on September 4,
2026. M6 may proceed under the decisions above.
