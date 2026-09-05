# M4 Case Runtime Review

Status: **Complete September 3, 2026**

M4 establishes the durable, model-independent runtime required before evidence
tools or agents are introduced.

## Delivered boundaries

| Area | Delivered behavior |
|---|---|
| Schemas | `case_management` and `ai_runtime` are created by Alembic revision `20260903_0003` |
| Intake | `POST /api/cases` atomically creates a case, two initial events, and one processing job |
| Idempotency | `(source, external_request_key)` is unique; a canonical SHA-256 fingerprint distinguishes retry from conflicting reuse |
| Identity | A claimed customer reference is linked when found but is never treated as authoritative merely because the complaint supplied it |
| Case history | Current status is a projection backed by immutable, per-case sequenced events |
| Job delivery | Eligible rows are leased with `FOR UPDATE SKIP LOCKED`; expired leases can be reclaimed |
| Failure handling | Transient failures receive bounded exponential retry; permanent or exhausted work is dead-lettered and escalated to human investigation |
| Mutations | Action intents, approvals, and execution attempts have separate durable records and idempotency boundaries |
| Authentication | One operations account, salted `scrypt` password hashes, hashed expiring bearer sessions |
| AI artifacts | Runs, plans, evidence, retrievals, proposals, and verification results are explicit records; no model is called in M4 |
| Simulator | Still a separate future process; no simulator control or status exists in the employee API |

## Verification evidence

- A repeated identical API request returns the original case with HTTP 200; the
  first request returns HTTP 201.
- Reusing the same source-scoped idempotency key with changed content returns a
  conflict and creates no second job.
- Two concurrent workers cannot claim the same row while its lock is held.
- A second worker can reclaim the same job after the original lease expires, with
  the attempt counter incremented.
- A permanent processing failure dead-letters the job, opens an escalation, and
  transitions the case to `human_investigation`.
- Employee case-list access is rejected without a valid session and succeeds after
  login.
- Alembic schema comparison reports no difference from SQLAlchemy metadata.
- Full verification result: 20 tests passed; Ruff formatting/lint and strict mypy
  passed.

## Intentional deferrals

- LangGraph checkpoint tables arrive with graph execution in M6, not before.
- No agent, embedding, policy ranking, or external model dependency exists yet.
- The standalone 10-20 second ticket simulator and operations dashboard arrive in
  M9, after the resolution path is trustworthy.
- Production identity federation, roles, and fine-grained IAM remain future scope;
  the MVP deliberately uses one all-permission operations account.
