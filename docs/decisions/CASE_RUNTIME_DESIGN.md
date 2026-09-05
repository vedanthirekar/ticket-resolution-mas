# Case Runtime and Durable Processing Design

Status: M4 implementation contract

This design begins after Gate C. It does not change the frozen `luma_business_v1`
business or knowledge data; it adds the operational shell that accepts and tracks
support cases.

## 1. Ownership boundaries

- `business.*` and `knowledge.*` remain authoritative evidence systems.
- `case_management.*` owns case lifecycle, durable work delivery, proposed
  mutations, approvals, execution attempts, and escalations.
- `ai_runtime.*` owns reproducible AI-run artifacts. It is evidence about what the
  AI did, not the source of business truth.
- LangGraph checkpoints will later own resumable graph execution only. A checkpoint
  will never replace the case, action, approval, or audit records.

Manual intake and the standalone simulator call the same `POST /api/cases`
contract. The simulator remains a separate process and will not appear in or be
controlled from the employee dashboard.

## 2. Intake contract

An intake request contains a stable source-scoped idempotency key, complaint text,
an optional claimed customer reference, source, and priority. Creation of the case,
its `case_received` event, and its first processing job occurs in one PostgreSQL
transaction.

The claimed customer reference is an allegation until matched to an existing
customer. An unknown reference does not reject intake; it produces a case with no
verified `customer_id`, which the future workflow must send to human investigation
if identity cannot be established from existing data.

The database stores a canonical request fingerprint. Reusing an idempotency key
with identical content returns the original case. Reusing it with different
content is a conflict.

## 3. Case lifecycle

```text
RECEIVED -> QUEUED -> PROCESSING
                         |---> RESOLVED
                         |---> PENDING_APPROVAL -> RESOLVED
                         |---> HUMAN_INVESTIGATION
                         `---> FAILED
```

Every accepted transition appends a sequenced immutable case event while updating
the current-state projection. No `WAITING_FOR_CUSTOMER` state exists in v1.

## 4. Durable job delivery

PostgreSQL is the MVP queue. Workers claim one eligible job under a row lock using
`FOR UPDATE SKIP LOCKED`, set an owner and lease expiry, and increment the attempt
count. This provides:

- one claimant per job at a time;
- horizontal worker concurrency without a separate broker;
- recovery of abandoned work when a lease expires;
- scheduled retry for transient failures;
- terminal dead-lettering for permanent failures or exhausted attempts.

Leases are delivery guarantees, not exactly-once execution. Future mutations must
also use action-level idempotency keys and deterministic preconditions.

## 5. Authentication scope

The MVP has one operations account with all employee-side permissions. Passwords
use salted `scrypt` hashes and bearer session tokens are stored only as SHA-256
hashes with expiry. This is deliberately narrow; production expansion would add an
external identity provider, roles, scoped permissions, audit review, rotation, and
revocation policy.

## 6. Persisted AI artifacts

`ai_runtime` reserves explicit records for case runs, investigation plans,
evidence, policy retrievals, resolution proposals, and verification results. These
records support debugging and evals without forcing later agents to encode durable
state inside prompts or opaque trace payloads. The tables are created in M4 but are
not populated by a model until M6.
