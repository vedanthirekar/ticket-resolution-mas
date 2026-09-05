# Agentic Case Resolution Engine - Implementation Plan

## 1. Purpose and planning approach

This plan turns the decisions in `PROJECT_DESIGN.md` into an executable build
sequence. It intentionally has two levels of detail:

1. A complete roadmap through the finished multi-agent product.
2. Task-level detail for the initial data-first milestone.

The first execution checkpoint ends after the fictional business, policies,
PostgreSQL schema, synthetic operational history, validation suite, and case
resolvability analysis are complete and frozen as `luma_business_v1`.

The downstream agent plan will then be refined against the actual frozen schema and
records. This avoids specifying agent behavior around fields that do not exist or
creating operational data to conveniently satisfy an already-written prompt.

## 2. Locked constraints carried from the design record

- The company is the fictional multi-location service business Luma Wellness.
- PostgreSQL is the only database system in the MVP.
- pgvector and PostgreSQL full-text search run inside PostgreSQL.
- SQLAlchemy 2.x is the application data layer, Psycopg 3 is the PostgreSQL driver,
  and Alembic owns schema migrations.
- LangGraph `StateGraph` is the sole multi-agent workflow orchestrator.
- LangChain is used selectively for model and tool integration inside graph nodes.
- The initial implementation uses one fixed model configuration; model routing is
  deferred.
- The runtime is provider-configurable, but only one provider adapter must work for
  the first end-to-end version.
- Operational evidence is retrieved using deterministic, typed relational tools.
- Policy evidence uses hybrid RAG with metadata filters, lexical retrieval, vector
  retrieval, and rank fusion.
- Agents never receive arbitrary SQL access.
- All mutations require human approval in the MVP.
- Missing, conflicting, unsupported, or unverifiable cases require human
  investigation.
- Customer follow-up and `WAITING_FOR_CUSTOMER` are deferred.
- The company UI has one operations account.
- Engineering evals and raw AI performance views are separate from the employee UI.
- The standalone simulator is independent from the dashboard and submits through
  the same API as manual intake.
- Hosting is deferred.
- A single-resolver comparison is deferred until the primary multi-agent system is
  complete and reliable.

## 3. Delivery strategy

### 3.0 Current progress

- **M0 - Local Infrastructure: complete (September 3, 2026).** PostgreSQL 16 with
  pgvector runs locally through Docker Compose. The initial Alembic migration,
  async SQLAlchemy/Psycopg connectivity, health check, linting, type checking, and
  database integration tests are verified.
- **M1 - Business Specification and Data Contract: complete (September 3, 2026).**
  Business rules, state machines, event semantics, invariants, versioned policies,
  evidence requirements, and outcome vocabulary are documented and consistency
  tested.
- **Gate A: approved September 3, 2026.** The M1 decisions were accepted without
  amendment and the contract name is `luma_business_v1`.
- **M2 - Operational Schema and Policy Storage: implemented (September 3, 2026).**
  The `business` and `knowledge` schemas, standalone migration, SQLAlchemy models,
  refund safety service, ERD, data dictionary, example queries, and database
  integration tests are complete.
- **Gate B: approved September 3, 2026.** The relational schema and temporal policy
  storage decisions were accepted before generation began.
- **M3 - Synthetic Data, Validation, and Freeze: implemented (September 3, 2026).**
  The deterministic generator, policy parser, independent validators, controlled
  operational incidents, reproducibility test, frozen manifest, and
  case-resolvability matrix are complete. The frozen dataset fingerprint is
  `ab2455c33f90a2089dae8f7fb83ba2713395bdc1d62b93db36b29924a281b14e`.
- **Gate C: approved September 3, 2026.** The frozen dataset and resolvability
  matrix were accepted without amendment. M4 and M5 now treat
  `luma_business_v1` as an immutable upstream contract.
- **M4 - Case Ingestion, Durable Jobs, and Workflow Persistence: complete
  (September 3, 2026).** The model-free runtime implements transactional and
  idempotent intake, immutable case events, leased PostgreSQL jobs, retry and
  dead-letter behavior, the one-account session boundary, and persisted AI
  artifact tables.
- **M5 - Operational Tools and Hybrid Policy Retrieval: complete (September 3,
  2026).** Typed, bounded, customer-scoped evidence tools and hard-filtered
  PostgreSQL FTS/pgvector retrieval pass component tests. Offline retrieval
  recall@5 is 94.12% on 17 versioned questions.
- **Gate D: approved September 4, 2026.** Decisions and evidence are recorded in
  `docs/decisions/GATE_D_REVIEW.md`. M6 is authorized to proceed.
- **M6 - LangGraph Multi-Agent Workflow: complete (September 4, 2026).** The fixed
  graph provides typed planning, bounded operational investigation, deterministic
  evidence gates, hybrid policy assessment, a one-round supplemental edge,
  grounded proposals, PostgreSQL checkpoints, and idempotent stage artifacts. See
  `docs/decisions/M6_AGENT_WORKFLOW.md`.
- **M7 - Verification, Disposition, Approval, and Safe Execution: complete
  (September 4, 2026).** Deterministic pre-verification, an independent verifier,
  deterministic disposition, exact action intents, authenticated approval,
  LangGraph interrupt/resume, stale-state revalidation, and idempotent refund and
  membership correction execution are implemented. See
  `docs/decisions/M7_VERIFICATION_AND_ACTION_SAFETY.md`.
- **M8 - Evaluation and Observability: implemented (September 4, 2026).** A
  fingerprint-bound 60-case dataset, development/held-out splits, deterministic
  graders, tool-outage injection, exportable reports, trace metadata, structured
  logs, cost hooks, and audit queries are complete. See
  `docs/decisions/M8_EVALUATION_AND_OBSERVABILITY.md`.
- **Gate E: pending.** M8 must establish end-to-end quality and verifier metrics
  with the selected live model before product UI work is authorized by this gate.

### 3.1 Milestone map

| Milestone | Outcome | Detail level now |
|---|---|---|
| M0 | Reproducible repository and local infrastructure | Detailed |
| M1 | Luma business and policy specification | Detailed |
| M2 | PostgreSQL operational schema and policy storage | Detailed |
| M3 | Connected synthetic data, validation, and frozen v1 dataset | Detailed |
| M4 | Case ingestion, durable jobs, and workflow persistence | Detailed and implemented |
| M5 | Operational tools and hybrid policy retrieval | Detailed and implemented |
| M6 | LangGraph multi-agent workflow | Detailed and implemented |
| M7 | Verification, disposition, approval, and safe execution | Detailed and implemented |
| M8 | Evaluation and observability | Detailed and implemented; live run pending |
| M9 | Operations UI and standalone ticket simulator | Roadmap |
| M10 | Hardening, documentation, and interview presentation | Roadmap |

### 3.2 Review gates

Do not continue automatically from one major checkpoint to another. Review the
evidence produced by each gate.

```text
Gate A: Business specification approved
    -> schema implementation may begin

Gate B: Schema and policies approved
    -> data generation may begin

Gate C: luma_business_v1 passes integrity checks and is frozen
    -> case/tool design may begin

Gate D: deterministic tools and retrieval pass component evals
    -> multi-agent orchestration may begin

Gate E: multi-agent safety and quality thresholds pass
    -> product UI and demo polish may begin
```

## 4. Target repository structure

The exact module names may change, but responsibility boundaries should remain.

```text
.
|-- apps/
|   |-- api/
|   |   `-- main.py
|   |-- worker/
|   |   `-- main.py
|   `-- web/
|       `-- Next.js application
|-- src/
|   `-- luma/
|       |-- config.py
|       |-- domain/
|       |-- db/
|       |   |-- models/
|       |   |-- repositories/
|       |   `-- session.py
|       |-- agents/
|       |-- workflow/
|       |-- tools/
|       |-- retrieval/
|       |-- services/
|       `-- observability/
|-- migrations/
|-- business_spec/
|-- policies/
|-- data_generation/
|   |-- generators/
|   |-- fixtures/
|   |-- manifests/
|   `-- validate.py
|-- simulator/
|-- evals/
|   |-- datasets/
|   |-- graders/
|   |-- experiments/
|   `-- reports/
|-- tests/
|   |-- unit/
|   |-- integration/
|   |-- data_integrity/
|   `-- evals/
|-- docker-compose.yml
|-- pyproject.toml
|-- .env.example
|-- README.md
|-- PROJECT_DESIGN.md
`-- IMPLEMENTATION_PLAN.md
```

## 5. M0 - Repository and local infrastructure

### Objective

Create a reproducible development environment with one command for infrastructure
and predictable commands for migrations, seeding, tests, linting, and type checks.

### M0.1 Python project scaffold

Create `pyproject.toml` using `uv` with initial dependency groups.

Runtime dependencies for the data milestone:

```text
pydantic
pydantic-settings
sqlalchemy
psycopg[binary,pool]
alembic
faker
```

Development dependencies:

```text
pytest
pytest-asyncio
ruff
pyright or mypy
```

LangGraph, LangChain, model-provider, embedding, and LangSmith dependencies may be
declared later when their milestone starts. This keeps the initial dependency graph
small and prevents accidental framework-driven data design.

Tasks:

- Establish the `src/luma` package.
- Add typed settings loaded from environment variables.
- Add development, test, and seed configuration profiles.
- Add `.env.example` without secrets.
- Ensure secrets and local database volumes are ignored by version control.
- Pin a supported Python minor version.
- Add standard commands to the README.

### M0.2 Local PostgreSQL

Create Docker Compose configuration for a PostgreSQL image that includes pgvector.

Requirements:

- Named database such as `luma`.
- Separate non-superuser application and migration credentials where practical.
- Health check before dependent commands run.
- Named local volume.
- Port configurable from environment.
- `vector` extension enabled by migration, not by undocumented manual setup.
- UTC database timezone.

No Redis, MongoDB, Elasticsearch, Pinecone, Kafka, or hosted service is introduced.

### M0.3 Database access foundation

Implement:

- SQLAlchemy engine/session factory using Psycopg 3.
- Transaction context utilities.
- Alembic configuration using the same settings source.
- Naming conventions for constraints and indexes.
- Database connectivity health check.
- Test database configuration that cannot accidentally target the development
  database.

Decide and document synchronous versus asynchronous application sessions before
repository implementation. The current recommendation is async API/worker access,
while migrations and some seed operations may remain synchronous when simpler.

### M0.4 Quality gates

Configure:

- Ruff formatting and linting.
- Pyright or mypy strict-enough checking for domain and service code.
- Pytest markers for unit, integration, data-integrity, and live-model tests.
- A default test command that never invokes paid model APIs.
- Pre-commit hooks only if they do not slow iteration materially.
- GitHub Actions after local commands are stable.

### M0 acceptance criteria

- `docker compose up -d` starts healthy PostgreSQL.
- A clean environment can install dependencies from the lockfile.
- Alembic can upgrade an empty database and downgrade the initial revision.
- A test proves SQLAlchemy connects through Psycopg.
- Formatting, linting, type checking, and non-model tests have documented commands.
- No API key is required for this milestone.

## 6. M1 - Luma business and policy specification

### Objective

Define the fictional organization as a coherent operating business before creating
agent prompts, tools, support tickets, or evaluation outcomes.

### M1.1 Business profile

Create `business_spec/COMPANY.md` covering:

- Company purpose and service model.
- Three locations, their timezones, hours, and differences.
- Approximately fifteen providers/employees.
- Approximately twenty-five services and their duration/price characteristics.
- Customer lifecycle.
- Appointment lifecycle.
- Payment lifecycle.
- Membership lifecycle and credit accounting.
- Online-booking behavior.
- Operational audit expectations.

Avoid describing the AI system in this document. It should read like documentation
for an existing booking/payments business.

### M1.2 Operational state machines

Create explicit state diagrams or tables for:

#### Appointment

Candidate states:

```text
scheduled
confirmed
checked_in
completed
cancelled
no_show
```

Define valid transitions and which event establishes each transition.

#### Payment

Candidate states:

```text
created
authorized
captured
partially_refunded
refunded
voided
failed
```

Define the difference between amount, authorized amount, captured amount, refunded
amount, and refundable amount.

#### Membership

Candidate states:

```text
active
paused
cancelled
expired
```

Define credit grants, consumption, expiration, correction, and reversal as immutable
ledger entries.

### M1.3 Actor and event semantics

Define actor types independently from event meaning:

```text
customer
employee
system
external_provider
```

An employee recording a customer's cancellation must not be interpreted as the
employee initiating the cancellation. Appointment event fields should distinguish:

- Event author/actor
- Event type
- Initiating party where applicable
- Reason code
- Event timestamp
- Structured metadata

This is required to support realistic evidence interpretation and verifier cases.

### M1.4 Business invariants

Document enforceable rules before tables are written. Examples:

- A provider can only be assigned to a service they are qualified to perform.
- An appointment belongs to exactly one customer, location, and service.
- A refund cannot exceed the remaining captured amount.
- A membership-credit correction is a ledger entry, not a balance overwrite.
- A cancellation fee must link to its appointment or invoice obligation.
- Booking availability depends on provider qualification, schedule, location hours,
  service configuration, and online-booking settings.
- Event timestamps cannot violate impossible lifecycle ordering unless a deliberate
  data-quality anomaly is recorded and documented.

Classify each invariant as:

- Database constraint
- Transaction/service-layer rule
- Data-generator validation
- Agent-time evidence check

### M1.5 Policy corpus specification

Author policies as business documents, not as answers to support tickets.

Initial policy areas:

1. Cancellation and no-show
2. Payments and refunds
3. Membership credits
4. Online booking
5. Adjustments and approval
6. Package use/expiration only if packages remain in the background model

Every policy must include:

- Stable policy ID
- Human-readable title
- Version
- Effective date range
- Scope metadata
- Numbered logical sections
- Definitions
- Main rules
- Exceptions where operationally plausible
- Relationship to superseded versions

At least some policies should have multiple versions so temporal retrieval can be
tested. Exceptions must require real operational facts, not hidden labels.

### M1.6 Policy decision table

Create a deterministic reference table for business review, separate from agent
prompts. For example:

| Situation | Policy result | Required facts |
|---|---|---|
| Provider initiated cancellation, no fulfilled transfer | Fee should be refunded | Initiator, transfer history, capture state |
| Customer cancelled outside free window | Fee may be retained | Initiator, timestamps, notice window |
| Payment authorized but not captured | No refund can be issued | Payment lifecycle state |

This table validates policy consistency. It must not be placed in agent-accessible
runtime tables as a direct answer lookup.

### M1 acceptance criteria

- Company operations can be understood without referencing the agent system.
- Appointment, payment, membership, and booking state semantics are unambiguous.
- Event actor and initiating-party semantics are explicitly different.
- Policies contain version/effective-date metadata and stable section IDs.
- Business invariants are assigned to enforcement layers.
- The policy decision table contains no contradictions.
- The business and policy specification receives a design review before schema work.

## 7. M2 - PostgreSQL operational schema and policy storage

### Objective

Translate the approved business specification into a constrained relational model.
This milestone creates the existing organizational system over which the later AI
solution will be designed.

### M2.1 PostgreSQL namespaces

Create only the schemas needed at this stage:

```text
business
knowledge
```

Create `case_management`, `ai_runtime`, `evaluation`, and LangGraph checkpoint
tables in later milestones. This reinforces the data-first sequence.

### M2.2 Identity and naming rules

Use internal primary keys consistently and expose stable business references such
as `APPT-000882` where useful for tickets and tools.

Decide one convention before migrations:

- UUID primary keys plus unique human-readable public references, recommended; or
- Stable prefixed string primary keys for every table.

The recommendation is UUID internal keys and unique public references. Agent tools
should normally accept public references and return both only where necessary.

Requirements:

- Constraint and index names follow the configured SQLAlchemy naming convention.
- Enumerations use constrained strings or PostgreSQL enums consistently.
- All mutable tables contain creation/update timestamps as appropriate.
- Immutable event/ledger tables do not pretend to support in-place business edits.
- Monetary values use integer cents and ISO currency codes.
- Times are stored as timezone-aware timestamps.

### M2.3 Core organization tables

Candidate tables:

```text
business.locations
business.location_business_hours
business.employees
business.employee_locations
business.services
business.location_services
business.employee_services
business.employee_schedules
business.customers
```

Important constraints:

- Unique public references.
- Valid timezone and currency representation.
- Positive service duration and price.
- Employee/service/location relationships required for bookability.
- Schedule end after start.

### M2.4 Appointment model

Candidate tables:

```text
business.appointments
business.appointment_events
```

`appointments` stores the current operational projection. `appointment_events`
stores immutable history.

Minimum appointment fields:

- Internal ID and public reference
- Customer, location, service, and employee references
- Scheduled start/end
- Current status
- Booking channel
- Created timestamp
- Optional cancellation timestamp and normalized current reason

Minimum event fields:

- Appointment reference
- Event type
- Author actor type and actor reference where available
- Initiating party where applicable
- Reason code
- Occurred timestamp
- Structured metadata JSONB
- Correlation/external reference where appropriate

### M2.5 Invoice and payment model

Candidate tables:

```text
business.invoices
business.invoice_items
business.payments
business.payment_events
business.refunds
```

Model distinctions among:

- Service price
- Cancellation/no-show fee obligation
- Payment authorization
- Capture
- Void
- Refund
- Partial refund

Important constraints and service rules:

- Payment currency matches the obligation.
- Refund references a captured payment.
- Aggregate completed refunds cannot exceed captured amount.
- External/mock processor references are unique when present.
- Idempotency keys are unique for mutation operations.

### M2.6 Membership model

Candidate tables:

```text
business.membership_plans
business.memberships
business.membership_ledger
```

Ledger entry types may include:

```text
grant
consume
expire
adjustment
reversal
```

Each entry records:

- Signed credit delta
- Effective timestamp
- Reason code
- Related appointment where applicable
- Reversal/related ledger entry where applicable
- Actor/source

The authoritative balance is derived from ledger entries. A cached balance may be
added only with reconciliation tests.

### M2.7 Booking configuration

Candidate tables:

```text
business.booking_settings
business.location_service_settings
business.employee_booking_settings
```

Document precedence when settings exist at multiple scopes. For example:

```text
company default
  -> location override
  -> service/location override
  -> employee override
```

The system must be able to explain why an otherwise valid provider/service/time is
not available online.

### M2.8 General audit events

Use a general business audit table only for cross-domain operational auditing that
is not already fully represented by a domain event table.

Avoid duplicating every appointment event in two places without a clear purpose.
Define which table is authoritative for each fact.

### M2.9 Policy storage

Candidate tables:

```text
knowledge.policy_documents
knowledge.policy_versions
knowledge.policy_sections
knowledge.policy_section_links
```

Policy sections include:

- Stable policy/version/section identifiers
- Hierarchy/parent section
- Heading and body
- Effective date and scope fields inherited or denormalized from version
- Lexical search vector
- Embedding column with dimension deferred until embedding model selection
- Content checksum

The initial migration may create the vector extension and nullable embedding field
later when its dimension is known. Do not pick an embedding dimension accidentally.

### M2.10 Indexes and access patterns

Create indexes from documented queries, including:

- Customer appointments ordered by time
- Appointment event history ordered by occurrence
- Payment by appointment/invoice/customer
- Refunds by payment and status
- Membership ledger by membership and effective time
- Employee schedules by employee and range
- Booking settings by scope
- Policy versions by effective range and status
- Policy sections by lexical search representation

Vector indexes may wait until data volume and embedding behavior justify them;
exact pgvector search is sufficient for a very small policy corpus.

### M2.11 Data dictionary and ER diagram

Generate or maintain:

- `business_spec/DATA_DICTIONARY.md`
- `business_spec/ERD.md` using Mermaid or another source-controlled format
- Notes explaining authoritative versus derived fields
- Example queries that demonstrate core relationships

### M2 acceptance criteria

- Alembic creates `business` and `knowledge` from an empty database.
- All documented foreign keys, unique constraints, checks, and indexes exist.
- Representative appointment, payment, refund, membership, and policy records can
  be inserted within valid transactions.
- Invalid representative records fail at the correct enforcement layer.
- Schema downgrade/rebuild works in a disposable test database.
- ER diagram and data dictionary match the migration.
- No case, AI, or eval answer columns exist in the operational schema.

## 8. M3 - Synthetic operational data, validation, and freeze

### Objective

Create a reproducible, causally connected business history with both ordinary
background activity and controlled operational anomalies. Validate it independently
and freeze a version before designing runtime tools or support cases.

### M3.1 Generator architecture

Use deterministic generators with a fixed seed and fixed reference clock.

```text
generate organizations and catalog
    -> generate customers and memberships
    -> generate schedules and booking configuration
    -> generate appointment lifecycles
    -> derive invoices and payment lifecycles
    -> generate membership ledger effects
    -> inject controlled operational incidents
    -> reconcile projections and ledgers
    -> validate
```

Do not use the current wall clock inside deterministic generation. Record:

```text
dataset_version
generator_version
random_seed
reference_time
alembic_revision
```

### M3.2 Target scale

Initial targets, adjustable after performance measurement:

| Entity | Target |
|---|---:|
| Locations | 3 |
| Employees/providers | 15 |
| Customers | about 300 |
| Services | about 25 |
| Appointments | about 2,000 |
| Appointment events | 3,000+ |
| Payments | about 1,500 |
| Memberships | about 150 |
| Policy documents/versions | enough to cover versioning and exceptions |

Exact counts are not acceptance criteria. Relationship quality and reproducibility
are more important.

### M3.3 Background operational data

Generate realistic variation:

- Locations with different hours and selected service availability.
- Providers qualified for subsets of services and locations.
- Employees with different schedules and time off.
- Customers with different join dates and activity frequency.
- Appointments across completed, upcoming, cancelled, and no-show states.
- Bookings from web, employee, and other plausible channels.
- Successful, failed, authorized-only, captured, voided, and refunded payments.
- Active, paused, cancelled, and expired memberships.
- Online-booking settings at multiple precedence levels.
- Policy versions that were applicable during different historical periods.

Distributions should be configured in one place and included in the dataset
manifest.

### M3.4 Controlled operational incidents

Create a small set of hand-designed canonical incidents inside the larger history.
These are business events, not yet support tickets.

Required incident families:

- Provider-initiated cancellation with an incorrectly captured fee.
- Customer-initiated cancellation inside and outside policy windows.
- No-show with a valid fee.
- Authorized but never captured fee.
- Duplicate captured payment against one obligation.
- Similar-looking payments that are legitimately distinct.
- Duplicate membership-credit consumption.
- Correct membership consumption disputed by the customer.
- Online booking disabled by provider override.
- Online booking unavailable because of qualification, schedule, or location rules.
- Missing audit evidence.
- Conflicting operational records.
- Policy version boundary cases.
- A policy exception requiring a supplemental operational fact.

The generator may keep an isolated build manifest describing which records were
deliberately created and why. This manifest is not loaded into agent-readable
schemas and is not treated as a runtime answer table. It later helps construct and
audit eval ground truth.

### M3.5 Data integrity validation

Create executable checks covering at least:

#### Referential integrity

- No orphan operational references.
- Public references are unique and correctly formatted.
- Cross-entity references belong to compatible customers/locations.

#### Appointment integrity

- Current status agrees with event history.
- Scheduled end follows start and duration is plausible.
- Provider qualification/location assignment is valid.
- Initiating party is not inferred solely from event author.

#### Financial integrity

- Amounts are non-negative where required.
- Captures do not exceed authorized values unless explicitly modeled and documented.
- Refunds do not exceed captured refundable values.
- Duplicate-payment incidents are distinguishable from legitimate separate
  obligations.

#### Membership integrity

- Ledger arithmetic reconciles.
- Reversals reference valid entries.
- Consumption references eligible appointments where required.
- Deliberate duplicate consumption is detectable from records rather than labels.

#### Booking integrity

- Effective setting precedence produces known bookability outcomes.
- Schedule, qualification, location, and service configuration can each independently
  explain unavailability in canonical records.

#### Policy integrity

- Version date ranges are coherent.
- Stable section IDs are unique within a version.
- Supersession links are valid.
- Canonical event dates map to exactly the intended applicable policy unless the
  incident deliberately models policy conflict.

### M3.6 Reproducibility test

From an empty disposable database:

1. Apply migrations.
2. Run generator with the recorded seed/reference time.
3. Run integrity validation.
4. Export stable row counts and canonical record references.
5. Rebuild again and compare the manifest/checksums.

Nondeterministic UUID generation must be controlled or excluded from checksums in a
documented manner. Prefer deterministic UUID derivation for generated fixtures.

### M3.7 Dataset freeze

Create `data_generation/manifests/luma_business_v1.json` containing:

```json
{
  "dataset_version": "luma_business_v1",
  "generator_version": "1.0.0",
  "seed": 20260903,
  "reference_time": "2026-09-01T12:00:00Z",
  "alembic_revision": "<revision>",
  "row_counts": {},
  "canonical_record_references": {},
  "validation_summary": {},
  "checksums": {}
}
```

After freezing:

- Schema or generator changes require `luma_business_v2` or an explicit rebuild of
  v1 before agent eval results can be compared.
- Eval results always record their dataset version.
- The runtime never reads canonical incident labels or expected outcomes.

### M3.8 Case-resolvability matrix

Inspect the frozen schema and data, then create
`business_spec/CASE_RESOLVABILITY.md`.

For every intended case family, record:

- Customer allegation
- Required operational facts
- Authoritative tables/fields
- Applicable policy topics
- Whether the current data can establish each fact
- Possible supported outcomes
- Reasons the case must escalate
- Facts that remain impossible to determine

This document is the formal bridge between the pre-existing business system and the
later AI solution.

### M3 acceptance criteria

- A clean database can reproduce `luma_business_v1` from code.
- Every integrity check passes except explicitly catalogued anomaly checks that
  assert the intended anomaly exists.
- The frozen manifest includes seed, clock, migration, counts, canonical references,
  and validation result.
- Canonical incidents are supported by causal operational records without answer
  labels in runtime schemas.
- Policies and operational timestamps permit temporal applicability testing.
- The case-resolvability matrix proves that the five MVP case families can be
  investigated from existing data.
- Runtime credentials cannot access isolated build/eval truth.
- Gate C review approves the data before tool or agent implementation begins.

## 9. M4 - Case ingestion, durable jobs, and workflow persistence

### Objective

Introduce the support-case system after the business snapshot is frozen.

Implemented tasks:

- Add `case_management` schema and migrations.
- Implement cases, case events, processing jobs, action intents, approvals,
  execution attempts, and escalations.
- Define case and job state-transition services.
- Implement transactional `POST /api/cases` creation of case plus processing job.
- Implement idempotent external request keys.
- Implement PostgreSQL job claiming with leases and `FOR UPDATE SKIP LOCKED`.
- Implement retry classification, maximum attempts, and terminal/dead-letter state.
- Add one operations account and simple authenticated session.
- Add `ai_runtime` schema for persisted AI artifacts.
- Add LangGraph PostgreSQL checkpoint tables only when graph execution begins.

Acceptance direction:

- Concurrent workers cannot claim the same lease.
- API retry cannot create duplicate cases.
- Worker crash permits job recovery after lease expiration.
- No model dependency is required yet.

Verification evidence is recorded in `docs/decisions/M4_RUNTIME_REVIEW.md`.

## 10. M5 - Operational tools and hybrid policy retrieval

### Objective

Expose the frozen business system through safe, typed evidence tools and create an
independently evaluable retrieval subsystem.

Implemented tasks:

- Implement Pydantic input/output contracts for every tool.
- Implement repository/service methods with customer/entity ownership checks.
- Add tool-call audit metadata and result truncation/pagination.
- Prevent broad customer enumeration and arbitrary SQL.
- Create policy-section embedding pipeline after selecting an embedding model.
- Implement hard effective-date/location/service filtering.
- Implement PostgreSQL full-text lexical ranking.
- Implement pgvector semantic ranking.
- Implement Reciprocal Rank Fusion.
- Fetch complete logical sections and linked definitions/exceptions.
- Build policy retrieval evals before integrating the Policy Agent.

Acceptance direction:

- Known IDs return exact authoritative records.
- Cross-customer lookups fail safely.
- Retrieval meets target recall@k on policy questions.
- Temporally inapplicable policies never pass hard filters.
- Every result carries source provenance.

Gate D evidence and the honest embedding-baseline limitation are recorded in
`docs/decisions/GATE_D_REVIEW.md` and
`docs/decisions/M5_TOOLS_AND_RETRIEVAL.md`.

## 11. M6 - LangGraph multi-agent workflow

### Objective

Implement the accepted graph with deterministic phase control and bounded agent
autonomy.

Roadmap tasks:

- Add provider-neutral model factory with one working provider.
- Define `CaseResolutionState` and all typed intermediate contracts.
- Implement Case Manager planning structured call.
- Validate required evidence using category rules plus agent plan.
- Implement Investigation Agent tool loop.
- Implement evidence completeness/conflict gate.
- Implement Policy Agent retrieval loop.
- Implement the allowlisted one-round supplemental evidence edge.
- Implement Case Manager proposal structured call.
- Persist artifacts and source IDs at every completed stage.
- Add stage-specific retry, turn, tool-call, timeout, and token limits.
- Use `case_run_id` as graph execution identity.

No model-routing optimization is included initially. Use one configured model or a
fixed per-role configuration and establish a baseline.

Acceptance direction:

- Happy paths reach a proposal with complete provenance.
- Missing/conflicting evidence terminates safely.
- Supplemental policy evidence runs no more than once.
- Completed stages are not repeated after a later transient failure.
- Graph state can resume after process restart.

## 12. M7 - Verification, disposition, approval, and execution

### Objective

Complete the safety and action lifecycle around agent proposals.

Roadmap tasks:

- Implement deterministic pre-verification.
- Implement adversarial Verifier Agent with actual source records.
- Route verifier failures to human investigation without an agent debate loop.
- Implement deterministic disposition rules.
- Convert verified mutations into immutable/idempotent ActionIntent records.
- Split action-intent creation, approval interrupt, revalidation, and execution into
  separate graph nodes.
- Persist approval/rejection by the single operations account.
- Resume graph execution after approval.
- Re-read and revalidate current business state before mutation.
- Implement mock `refund_payment` and `adjust_membership_credit` transactions.
- Create business audit events and deterministic execution receipts.
- Generate grounded customer-safe response text only from verified/executed state.

Acceptance direction:

- No mutation occurs without approval.
- Duplicate execution is impossible through idempotency constraints and service
  behavior.
- Stale approved actions fail safely or return already completed.
- LLM output cannot override a deterministic failure.
- Verifier catch rate and false-rejection rate are measurable.

## 13. M8 - Evaluation and observability

### Objective

Measure correctness, safety, retrieval, trajectory, cost, and reliability without
mixing builder metrics into the employee product.

Roadmap tasks:

- Create isolated `evaluation` schema or versioned dataset artifacts.
- Generate 50-60 eval tickets from frozen operational truth.
- Split development and held-out cases.
- Add happy-path, boundary, counterfactual, adversarial, and tool-failure cases.
- Implement deterministic graders first.
- Add trajectory/tool graders.
- Add limited semantic graders for grounded explanation quality.
- Measure policy recall, evidence completeness, decision accuracy, escalation,
  verifier behavior, unauthorized actions, latency, tool calls, tokens, and cost.
- Add LangSmith traces and experiment metadata.
- Keep repository datasets and reports authoritative/exportable.
- Add structured application logs and business audit queries.

Implemented details and the frozen Gate E thresholds are recorded in
`docs/decisions/M8_EVALUATION_AND_OBSERVABILITY.md`. The source-controlled dataset is
`evals/datasets/luma_cases_v1.json`; the CLI is `luma-eval`. The evaluator never
auto-approves actions, so repeated quality runs do not mutate frozen operational
truth. Actual model-quality claims remain pending a configured live provider.

Acceptance direction:

- Unauthorized action and duplicate execution rates are zero.
- Guardrail tests pass completely.
- Target resolution accuracy and unsafe-case escalation recall are met or failures
  are documented honestly.
- Every eval result records dataset, prompt, model, tool, and graph versions.
- A failed eval can be traced to exact model/tool/policy/evidence steps.

## 14. M9 - Operations UI and standalone simulator

Implementation status: complete. The authenticated operations product, durable
worker continuation, SSE invalidation stream, customer intake, and independent
simulator are implemented; see
`docs/decisions/M9_OPERATIONS_UI.md`.

### Objective

Expose the operational workflow as a credible service-business product and provide
an independent stream of synthetic intake.

Operations UI roadmap:

- Next.js/TypeScript application.
- One-account login.
- Operations overview.
- Filterable case queue.
- Case detail with evidence provenance and policy citations.
- Pending approval list and approve/reject actions.
- Human-investigation queue with precise reasons.
- Simplified operational timeline, not raw chain of thought.
- Server-Sent Events for case-state updates.
- No engineering eval/architecture-comparison page.
- No simulator controls or simulator-status panel.

Standalone simulator roadmap:

- Python process using only the standard library.
- Pre-generated JSON/JSONL complaint pool.
- Submit through `POST /api/cases` only.
- Random 10-20 second delay.
- Manual start/stop.
- Optional maximum case count.
- No runtime LLM generation.

Acceptance direction:

- Manually and simulator-submitted cases follow the identical backend path.
- A viewer can watch queued cases progress without refreshing.
- Approval resumes and completes the correct case.
- Simulator can be removed entirely without changing product behavior.

## 15. M10 - Hardening, documentation, and interview presentation

Implementation status: implemented. CI, architecture/sequence diagrams, threat and
production-readiness documentation, PII/logging rules, a guarded local reset/reseed
path, deterministic demo fallback, a source-controlled evaluation/error review, and
the interview narrative are present. Full live-model Gate E validation remains a
separate hold pending adequate provider quota and the deferred routing/prompt work.

### Objective

Turn the working implementation into a reliable, explainable interview artifact.

Roadmap tasks:

- Add complete local setup and demo instructions.
- Add architecture and sequence diagrams generated from source-controlled text.
- Add failure-mode and threat-model documentation.
- Add PII/redaction policy for traces.
- Add prompt/version change process.
- Add backup demo fixtures and deterministic replay where useful.
- Add CI for migrations, integrity tests, unit tests, and non-live evals.
- Produce eval report and error analysis.
- Prepare presentation narrative and demo script.
- Document prototype-to-production changes without implementing unnecessary cloud
  infrastructure.
- Consider hosting only after local reliability.
- Consider fixed-model versus routed-model and multi-agent versus single-resolver
  experiments only after the primary result is stable.

Final acceptance direction:

- A clean machine can run the documented local demo.
- The demo has a reliable reset/reseed path.
- The presentation can explain every AI component's inputs, outputs, and safety
  boundary.
- Metrics are generated from real eval runs, not hard-coded UI values.
- Known limitations and future scope are explicit.

## 16. Testing strategy by layer

### Unit tests

- Domain state transitions
- Money and refundable-balance calculations
- Membership ledger calculations
- Policy effective-date logic
- RRF implementation
- Model-independent routing edges
- Disposition and approval rules
- Idempotency-key construction

### Integration tests

- SQLAlchemy repositories against PostgreSQL
- Alembic upgrade/downgrade
- Job claiming and lease recovery
- API transaction boundaries
- pgvector and full-text retrieval
- LangGraph checkpoint/resume
- Approval interruption/resumption
- Mock action execution

### Data-integrity tests

- All M3 invariants
- Frozen manifest reproducibility
- Canonical incident existence
- No answer leakage in runtime schemas
- Runtime role cannot access evaluation truth

### Agent component evals

- Planning classification and evidence requirements
- Investigation tool selection/arguments
- Evidence completeness and provenance
- Policy retrieval and applicability
- Supplemental evidence-request precision
- Proposal correctness
- Verifier catch/false-rejection behavior

### End-to-end evals

- Final decision and amount
- Disposition
- Required and forbidden evidence
- Required and forbidden actions
- Database postconditions
- Approval and idempotency
- Latency, tool calls, tokens, and cost

## 17. Major risks and mitigations

| Risk | Mitigation |
|---|---|
| Synthetic data conveniently encodes answers | Freeze business schema/data before tickets; isolate incident/eval truth |
| Multi-agent complexity without measurable value | Evaluate each stage and preserve simple deterministic boundaries |
| Policy RAG retrieves current but inapplicable version | Hard effective-date/scope filters before ranking |
| Agent confuses event author with initiating party | Separate schema fields, business documentation, verifier cases |
| LangGraph checkpoint becomes hidden source of truth | Persist business artifacts in application tables; checkpoint only workflow execution |
| Approval resume duplicates side effects | Separate interrupt and mutation nodes; require idempotent executor |
| Worker crash loses or duplicates work | Job leases, checkpoint persistence, idempotency constraints |
| Free model has weak structured/tool behavior | Provider adapter, schema retries, eval gates, configurable model |
| UI consumes project time before quality is known | UI starts after multi-agent safety/eval gate |
| Eval set overfits prompts | Development/held-out splits and counterfactual cases |
| Raw traces expose synthetic-but-sensitive-looking data | Trace redaction/configuration and separate business audit |

## 18. Immediate execution boundary

The next implementation session should execute only M0 through M3:

```text
M0 repository/infrastructure
  -> review
M1 business and policy specification
  -> Gate A review
M2 schema and policy storage
  -> Gate B review
M3 generator, validation, freeze, and resolvability matrix
  -> Gate C review
```

Do not implement LangGraph agents during this checkpoint. The output of Gate C is
the input to the detailed tool and multi-agent implementation plan.

## 19. Open items that do not block M0-M3

- First model provider and exact model
- Embedding provider/model and vector dimension
- Exact LangGraph package versions
- Per-agent token, turn, and tool-call limits
- Final policy retrieval `top_k` and RRF constant
- Whether clear financial denials auto-resolve or receive an additional review rule
- Exact UI component library details
- Hosting
- Model routing
- Single-resolver comparison
