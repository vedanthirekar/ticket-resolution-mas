# M5 Evidence Tools and Policy Retrieval

Status: Implemented for Gate D review

## 1. Operational evidence boundary

The future Investigation Agent receives typed application tools, never database
credentials or arbitrary SQL. Each request is bounded by Pydantic validation and
each result includes a unique tool-call reference, execution time, source system,
result count, truncation flag, and record-level provenance.

| Tool | Human-system analogue | Boundaries |
|---|---|---|
| `get_customer` | Open the customer profile | Exact public reference; masked contact fields |
| `get_customer_appointments` | Review booking history | Exact customer; maximum 50; optional time window |
| `get_appointment_timeline` | Open booking and audit timeline | Exact customer plus appointment ownership |
| `get_appointment_payments` | Review invoice, charge, provider events, and refunds | Exact customer-owned appointment |
| `get_membership_evidence` | Review membership terms and immutable credit ledger | Exact customer; as-of time; bounded complete ledger |
| `get_customer_booking_attempts` | Find retained web/mobile submissions | Exact customer; bounded time window |
| `get_booking_attempt_evidence` | Inspect why a submitted booking succeeded or failed | Exact customer-owned attempt plus effective configuration, hours, qualifications, schedule, blocks, resources, and conflicts |

Cross-customer requests return the same not-found boundary as nonexistent records,
so a caller cannot use a known appointment reference to enumerate another
customer's data. Complaint claims are never used to modify or override returned
facts.

## 2. Policy retrieval pipeline

```text
query + material event date + optional scope
        |
        v
hard SQL filters
  effective interval, non-draft status, policy ID/area,
  location/service scope
        |
        +--------------------+
        |                    |
 PostgreSQL FTS          pgvector cosine
 OR candidate query      768-d embedding
        |                    |
        +---------+----------+
                  v
       weighted reciprocal-rank fusion
                  |
                  v
  stable section IDs + version + full provenance
```

Temporal and scope rules are filters, not ranking hints. An inapplicable policy
cannot be rescued by a high text/vector score. Lexical candidates receive a 1.5
weight because exact policy vocabulary is especially valuable in this small,
controlled corpus; vector candidates receive 1.0. Ties are stable by section ID.

`fetch_policy_section` validates applicability again and expands the selected
section with its logical parent and applicable one-hop linked definitions,
exceptions, supersession, or related sections.

## 3. Embedding-provider decision

Storage uses `vector(768)` and an HNSW cosine index. Both indexing and querying use
the `EmbeddingProvider` protocol, including an exact model identity stamp on each
section.

No paid/external model was selected before M5. Offline tests therefore use
`luma-feature-hash-768-v1`, a deterministic feature-hashing baseline. It gives
repeatable vectors and exercises batching, dimension validation, pgvector search,
model-version filtering, and fusion. It is explicitly not presented as proof of
semantic embedding quality.

Before final production-quality evals, replace it with a real 768-dimensional
embedding adapter and rerun the unchanged retrieval dataset. This does not block
LangGraph design because the storage, provider interface, filtering, ranking, and
provenance contracts are already fixed.

## 4. Evaluation contract

`evals/datasets/policy_retrieval_v1.json` contains 17 questions spanning payment,
cancellation, membership, booking, approval, temporal versions, and escalation.
The initial Gate D threshold is retrieval recall@5 of at least 90%, zero temporal
filter violations, zero scope-filter violations, and zero cross-customer data
disclosures.

The one known miss is the generic membership-expiry wording. It remains visible in
the eval rather than being deleted or rewritten after seeing the result.
