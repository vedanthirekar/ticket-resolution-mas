# Agentic Case Resolution Engine — Living Design Record

## 1. Purpose of this document

This document preserves the design discussion for the project, including small but
important decisions that could otherwise be lost when implementation begins. It is
the current source of truth for:

- Product scope and interview narrative
- The fictional business and operational-data model
- AI and agent responsibilities
- Deterministic safety boundaries
- Multi-agent orchestration and a future single-resolver baseline
- Case-ingestion simulation
- Operations UI boundaries
- Evaluation and observability
- Decisions rejected or deferred
- Questions that remain open

This is a living design record, not a claim that every item is already implemented.
When a decision changes, update the relevant section and the decision log rather
than silently replacing the old rationale.

The executable milestone sequence is maintained separately in
`IMPLEMENTATION_PLAN.md`.

## 2. Project objective

Build a production-minded **Agentic Case Resolution Engine for Service Businesses**
using a fictional multi-location company named **Luma Wellness**.

The project is intended for an onsite AI Engineering interview. Its primary goal is
to demonstrate:

- Product and system-design judgment
- Appropriate boundaries between AI reasoning and deterministic software
- Tool-using agent design
- Relational data modeling and evidence provenance
- Guardrails, approvals, idempotency, and auditability
- Evaluation grounded in known truth
- Observability and failure analysis
- Awareness of production concerns and explicit prototype tradeoffs

The project is not primarily a chatbot and should not look like one.

The essential contrast is:

```text
Not:

Ticket → LLM → answer

Instead:

Ticket
  ↓
Investigate operational data
  ↓
Retrieve applicable policy
  ↓
Reason over sourced evidence
  ↓
Propose a resolution
  ↓
Verify the proposal
  ↓
Resolve safely, request approval, or escalate
```

## 3. Project thesis

The primary interview thesis is:

> Can a bounded multi-agent workflow investigate operational support cases,
> retrieve temporally applicable policy, and produce safe grounded resolutions
> while maintaining zero unauthorized actions within acceptable latency and cost?

The project will not assume that multi-agent architecture is automatically better.
The MVP first evaluates whether the chosen multi-agent workflow meets its own
quality and safety targets. A same-data single-resolver comparison remains a
valuable follow-up if time permits, and its result will be reported honestly even
if the simpler architecture wins.

## 4. Current decision status

### Accepted decisions

- Use Luma Wellness as the fictional service business.
- Use PostgreSQL, not SQLite, as the authoritative persistent store.
- Generate a tightly connected, primarily synthetic operational dataset.
- Design and freeze the business system before designing agent tools around it.
- Keep evaluation truth isolated from agent-accessible operational data.
- Accept cases through one API boundary.
- Support two independent intake producers:
  - Manual complaint submission
  - A standalone ticket simulator
- The simulator calls the case API and never writes directly to the database.
- The simulator is independent of the company dashboard and has no dashboard page,
  control, status widget, or other product integration.
- The simulator sends a case every randomly selected 10–20 seconds while manually
  running and stops when manually terminated.
- Use one company/operations account in the implemented demo.
- Preserve capability separation inside the system even though the human demo has
  only one account.
- Do not implement a request-more-information/customer follow-up loop in the MVP.
- Insufficient or ambiguous customer information leads to human investigation.
- Keep engineering AI-performance reports separate from the employee-facing
  product.
- Agents may propose actions; deterministic code authorizes and executes them.
- Revalidate state immediately before executing an approved action.
- Implement the manager/specialist multi-agent architecture first. Preserve a
  compatible strategy boundary, but defer the single-resolver baseline until the
  primary system is reliable and evaluated.
- Keep the verifier and proposal generator logically separate, subject to measuring
  whether verification earns its cost.
- Use a deterministic workflow orchestrator to control inter-agent phases and
  persist typed artifacts between them.
- Permit one bounded Policy Agent to Investigation Agent evidence-gap loop when an
  applicable policy introduces a fact that the initial investigation could not
  reasonably know was required.
- Do not implement a Verifier to Case Manager debate or repair loop in the MVP.
- Retrieve operational business records through narrow, deterministic relational
  tools backed by parameterized SQL, not conventional RAG or arbitrary model SQL.
- Retrieve policies with hybrid RAG: hard metadata/applicability filters, lexical
  full-text retrieval, semantic vector retrieval, rank fusion, and policy-agent
  interpretation.
- Use LangGraph `StateGraph` as the explicit multi-agent workflow orchestrator.
- Use LangChain selectively for model and tool integrations inside graph nodes,
  with a provider adapter (`langchain-google-genai` in the current build). Do not
  add a second overlapping orchestration framework.
- Use one PostgreSQL database system for operational data, cases, AI artifacts,
  policies and vectors, processing jobs, LangGraph checkpoints, and isolated eval
  truth. Separate PostgreSQL schemas do not represent separate database systems.
- Use SQLAlchemy 2.x as the application query/transaction layer, Psycopg 3 as the
  underlying PostgreSQL driver, and Alembic for schema migrations. Use explicit
  PostgreSQL SQL through SQLAlchemy where full-text, pgvector, or locking queries
  require it.
- Adopt the application stack recorded in Section 9.1, including FastAPI, a
  PostgreSQL-backed async worker, Server-Sent Events, Next.js/TypeScript, and
  repository-native traces/eval reports. LangSmith export remains optional.

### Proposed but not yet locked

- Exact model choices and reasoning settings for each agent role
- Exact policy embedding model and hybrid-retrieval parameters
- Four deeply implemented case families before adding more breadth

### Explicitly deferred

- Online hosting and cloud-provider selection
- Multiple employee roles and full IAM/RBAC implementation
- Customer follow-up conversations and a `WAITING_FOR_CUSTOMER` workflow
- Kafka or another high-scale event-streaming platform
- Real external payment or booking mutations
- Single-resolver baseline and architecture comparison until the multi-agent system
  is complete, reliable, and evaluated
- Extra agents added solely for architectural appearance
- Phoenix or another observability platform unless it adds demonstrated value
- MCP unless a concrete integration need appears

## 5. Product and system boundaries

The system is best understood as a deterministic case state machine containing a
few bounded AI decision points.

```text
AI reasoning plane
  Understand language, plan an investigation, interpret evidence and policy,
  and propose an outcome.

Control plane
  Verify support, enforce evidence requirements, calculate risk, require approval,
  and govern state transitions.

Execution plane
  Apply validated business changes safely and idempotently.
```

The model is not:

- The source of truth
- The authorization system
- The payment processor
- The database integrity layer
- The final arbiter of approval requirements
- The audit log

## 6. End-to-end workflow

```text
Case received
    ↓
Validate request and establish customer identity from trusted intake metadata
    ↓
Persist case and processing job atomically
    ↓
Worker claims job
    ↓
Classify case and build an investigation plan
    ↓
Collect operational evidence through read-only tools
    ↓
Retrieve policy applicable at the event time and location
    ↓
Propose a structured resolution
    ↓
Run deterministic checks and semantic verification
    ↓
Select disposition
    ├── AUTO_RESOLVED
    ├── HUMAN_APPROVAL_REQUIRED
    └── HUMAN_INVESTIGATION_REQUIRED
    ↓
For approved actions, reload and revalidate current state
    ↓
Execute idempotently
    ↓
Reconcile result, persist audit history, and prepare a grounded response
```

Retryable technical failures may temporarily enter internal retry/failed states,
but they are not business dispositions.

### Suggested workflow states

```text
RECEIVED
QUEUED
TRIAGING
INVESTIGATING
RETRIEVING_POLICY
PROPOSING_RESOLUTION
VERIFYING
AUTO_RESOLVED
PENDING_APPROVAL
HUMAN_INVESTIGATION_REQUIRED
EXECUTING
RESOLVED
FAILED_RETRYABLE
FAILED_TERMINAL
```

`WAITING_FOR_CUSTOMER` is intentionally excluded from the MVP. Missing identity,
appointment reference, policy, or other required evidence results in
`HUMAN_INVESTIGATION_REQUIRED` with a precise reason code.

## 7. Human workflow reflected by the system

The AI architecture should correspond to real support work rather than arbitrary
agent names.

| Human activity | System responsibility | AI? |
|---|---|---:|
| Read and categorize complaint | Triage and planning | Yes |
| Decide what records must be checked | Investigation planning | Yes |
| Open booking, customer, payment, and membership systems | Investigation agent using database tools | AI selecting deterministic reads |
| Search the internal handbook | Policy retrieval | Retrieval with optional AI query interpretation |
| Interpret facts and recommend an outcome | Resolution proposer | Yes |
| Review whether the recommendation is supported | Verifier | AI plus deterministic checks |
| Determine approval requirement | Disposition/risk engine | No |
| Apply refund or credit adjustment | Action executor | No |
| Explain verified outcome to customer | Grounded response writer | Yes, optional/bounded |

An agent is conceptually:

```text
model
+ instructions
+ allowed tools
+ working context
+ structured output contract
+ stopping and retry limits
```

## 8. Intake producers

### 8.1 Manual submission

A small complaint form or API client submits:

```json
{
  "source": "manual_web_form",
  "customer_id": "CUS-102",
  "complaint": "I was charged $80 even though the stylist cancelled.",
  "appointment_reference": "APPT-882",
  "submitted_at": "2026-09-03T15:10:00Z"
}
```

The API responds immediately:

```json
{
  "case_id": "CASE-4928",
  "status": "queued"
}
```

Case and processing job creation must be transactional.

### 8.2 Standalone simulator

The simulator is a separate Python process and is not part of the product UI.

```text
Manual complaint form ─┐
                      ├─→ POST /api/cases → Postgres → worker
Standalone simulator ─┘
```

Simulator behavior:

1. Select a complaint from a prepared ticket pool.
2. Submit it through `POST /api/cases`.
3. Wait a random interval from 10 through 20 seconds.
4. Repeat until manually stopped, optionally respecting a case limit.

Implemented commands:

```powershell
uv run luma-simulator
uv run luma-simulator --min-interval 10 --max-interval 20
uv run luma-simulator --count 20
```

The simulator:

- Never writes directly to Postgres.
- Does not expose controls in the operations dashboard.
- Does not appear as a product feature to company employees.
- May record `source=simulator` for debugging and demo filtering.
- Uses pre-generated complaints rather than spending model tokens generating new
  complaints at runtime.

Future intake producers could include a Zendesk webhook, email parser, CRM, SMS, or
mobile application without changing the core processing boundary.

## 9. Why PostgreSQL fits this project

The operational truth is highly relational:

```text
customer
  └── appointment
        ├── appointment events
        ├── employee
        ├── service
        ├── location
        └── payment
              └── refund

case
  ├── evidence
  ├── policy version and section
  ├── proposed action
  ├── verification
  ├── approval
  └── execution attempts
```

PostgreSQL provides:

- Foreign-key integrity across related operational records
- Transactions for multi-record state changes
- Row locking for concurrent workers and approvals
- Uniqueness constraints for idempotency
- Relational reporting and aggregation
- JSONB for evolving agent artifacts
- Optional full-text search and pgvector
- A realistic local-to-hosted migration path

MongoDB could implement the project, including references and transactions, but the
domain contains dense relationships, financial state, ledgers, and cross-record
invariants. A document-first model would move more integrity work into application
code or duplicate operational information. PostgreSQL is selected for domain fit,
not merely to appear production-like.

Money must be stored in integer minor units such as cents, never floating point.
Timestamps should be stored in UTC, with relevant business timezones recorded.

### 9.1 Chosen technology stack and database layering

The MVP uses one PostgreSQL database system. The surrounding names are layers or
capabilities, not additional databases:

```text
Python application
    ↓
SQLAlchemy 2.x: query construction, mappings, sessions, and transactions
    ↓
Psycopg 3: PostgreSQL protocol driver and connection layer
    ↓
One PostgreSQL database
    ├── business operational tables
    ├── case-management and job tables
    ├── AI artifact tables
    ├── policy text and full-text indexes
    ├── pgvector embedding columns/indexes
    ├── LangGraph checkpoint tables
    └── isolated evaluation truth
```

- PostgreSQL is the database.
- pgvector is an extension inside PostgreSQL, not a separate vector database.
- PostgreSQL full-text search is a built-in database capability.
- Psycopg is the low-level Python PostgreSQL driver.
- SQLAlchemy is the higher-level application database toolkit and uses Psycopg
  underneath.
- Alembic versions and applies schema migrations using SQLAlchemy metadata and
  explicit migration operations.
- The LangGraph Postgres checkpointer creates workflow-state tables in the same
  PostgreSQL system.
- A PostgreSQL-backed job queue is implemented with ordinary tables, leases, and
  row locking; it is not Redis, RabbitMQ, or Kafka.

The application normally uses SQLAlchemy repositories and transactions. Carefully
written PostgreSQL-specific SQL remains appropriate through SQLAlchemy for
full-text ranking, pgvector similarity, `FOR UPDATE SKIP LOCKED`, and other features
where explicit SQL is clearer.

Chosen application stack:

| Layer | Technology |
|---|---|
| Language/runtime | Python 3.12+ |
| Workflow orchestration | LangGraph `StateGraph` |
| Agent/model integration | LangChain core plus swappable Gemini/OpenRouter adapters; current default is an OpenRouter `:free` model |
| Agent contracts | Pydantic v2 structured models |
| API | FastAPI and Uvicorn |
| Persistence | PostgreSQL with pgvector |
| Python data access | SQLAlchemy 2.x over Psycopg 3 |
| Migrations | Alembic |
| Background processing | Python async worker with PostgreSQL job leasing |
| Live product updates | Server-Sent Events |
| Operations UI | Next.js, TypeScript, and a source-controlled CSS design system |
| Agent tracing/eval experiments | Repository reports and structured logs; optional LangSmith export |
| Tests | pytest and pytest-asyncio |
| Local environment | Docker Compose and `uv` |
| Quality tooling | Ruff and Pyright or mypy |

Do not combine LangGraph with a second overlapping orchestration runtime. Model
providers remain replaceable behind the structured-model adapter.

## 10. Data-first design principle

The business system must be designed and frozen before the agent tools and eval
cases are created. The project should genuinely exhibit this order rather than only
claiming it in a presentation.

### Phase 1: Define the fictional business

Document independently of the agents:

- Locations and operating hours
- Employees, qualifications, and schedules
- Services and location availability
- Appointment creation and lifecycle
- Cancellation and no-show processes
- Invoices, payments, captures, and refunds
- Membership plans and credit accounting
- Online-booking configuration
- Operational audit events
- Internal business policies

### Phase 2: Design the operational database

Proposed PostgreSQL schemas:

```text
business.*
  Existing operational system

case_management.*
  Support cases and resolution workflow

ai_runtime.*
  Plans, evidence, proposals, verification, and run metadata

evaluation.*
  Hidden eval cases and expected outcomes
```

Proposed operational tables:

```text
business.customers
business.locations
business.employees
business.services
business.employee_services
business.employee_schedules
business.appointments
business.appointment_events
business.invoices
business.payments
business.payment_events
business.refunds
business.membership_plans
business.memberships
business.membership_ledger
business.packages
business.package_ledger
business.booking_settings
business.audit_events
```

Proposed case-management tables:

```text
case_management.cases
case_management.case_events
case_management.processing_jobs
case_management.action_intents
case_management.approvals
case_management.execution_attempts
case_management.escalations
```

Proposed AI-runtime tables:

```text
ai_runtime.case_runs
ai_runtime.investigation_plans
ai_runtime.evidence_items
ai_runtime.policy_retrievals
ai_runtime.resolution_proposals
ai_runtime.verification_results
```

Evaluation tables are inaccessible to runtime agents:

```text
evaluation.eval_cases
evaluation.required_evidence
evaluation.expected_policy_citations
evaluation.expected_outcomes
```

The agent/runtime database role should have:

```text
READ business.*
READ/WRITE case_management.* through application services
READ/WRITE ai_runtime.* through application services
NO ACCESS evaluation.*
```

The operational schema must not contain answer-leaking fields such as:

```text
should_refund
expected_resolution
is_duplicate
credits_wrong
should_escalate
```

### Phase 3: Write independent business policies

Policies should resemble documents the company already uses:

- Cancellation and No-Show Policy
- Payment and Refund Policy
- Membership Credit Policy
- Package Expiration Policy
- Online Booking Policy
- Adjustment and Approval Policy

Each policy requires:

- Stable policy ID
- Version
- Section IDs
- Effective start and end dates
- Location or jurisdiction applicability where needed
- Supersession relationship where needed

Retrieval must find the policy that was effective at the time of the disputed event,
not simply the newest or most semantically similar document.

### Phase 4: Generate connected operational history

The generator should create roughly:

| Entity | Initial target |
|---|---:|
| Locations | 3 |
| Employees/providers | 15 |
| Customers | 300 |
| Services | 25 |
| Appointments | 2,000 |
| Payments | 1,500 |
| Memberships | 150 |
| Packages | 100 |
| Audit/events | 3,000+ |
| Policies | 10–15 sections/documents as appropriate |

Counts are adjustable. Referential and causal quality is more important than size.

Required integrity properties include:

- Appointments reference existing customers, services, locations, and qualified
  providers.
- Appointment times respect operating hours and schedules unless a deliberately
  modeled anomaly explains otherwise.
- Payment and refund timing follows the operational lifecycle.
- Refunds never exceed captured refundable value.
- Membership ledger entries reconcile to balances.
- Appointment state is consistent with appointment events.
- Every deliberate anomaly is created through realistic records, not answer labels.

Example duplicate-payment evidence:

```text
PAY-101: $120 captured for APPT-500
PAY-102: $120 captured for APPT-500 fourteen seconds later
Only one valid invoice obligation exists
```

Example membership discrepancy:

```text
+4 monthly credits
-1 attended appointment
-1 accidental duplicate attendance deduction
Current balance: 2
Correct balance after reversing duplicate: 3
```

Example cancellation dispute:

```text
Appointment event: cancelled
Actor: employee
Reason: provider_unavailable
Payment: cancellation fee captured
Applicable policy: provider-initiated cancellations must not incur the fee
```

### Phase 5: Validate and freeze business data

Create a reproducible data version such as:

```text
dataset_version = luma_business_v1
seed = 20260903
```

Expected artifacts:

- Business specification
- Data dictionary
- Entity-relationship diagram
- Alembic migrations
- Reproducible seed generator
- Integrity-test suite and report
- Policy corpus
- Versioned database snapshot or deterministic rebuild instructions

### Phase 6: Analyze case resolvability

Only after the business data is frozen, determine what the available records can
support:

| Case type | Existing evidence required | Initial assessment |
|---|---|---:|
| Cancellation-fee dispute | Appointment, events, payment, applicable policy | Resolvable |
| Duplicate payment | Payment records, invoice obligation, associations | Resolvable |
| Membership-credit dispute | Membership ledger and attendance | Resolvable |
| Booking unavailable | Schedule, qualification, service, settings | Resolvable |
| Injury compensation | Incident/insurance records not modeled | Escalate |

This matrix demonstrates that the AI system was designed as an integration over an
existing organizational model.

### Phase 7: Build safe read tools

Tools adapt the frozen business schema into typed, bounded responses:

```text
get_customer
get_appointments
get_appointment
get_appointment_events
get_payments
get_payment_for_appointment
get_membership
get_membership_ledger
get_employee_schedule
get_service_configuration
get_booking_configuration
search_policy
fetch_policy_section
```

Agents do not receive arbitrary SQL access.

### Phase 8: Create tickets and evaluation truth

Eval complaints are produced after the operational truth is fixed. Expected results
are derived into the isolated evaluation schema or versioned dataset files.

The honest presentation narrative is:

> I first modeled and generated a versioned operational system for a fictional
> multi-location wellness business. I validated and froze that business-data
> contract. I then designed the case-resolution engine as an integration over the
> available operational records and policies. Evaluation truth is isolated from
> every agent-accessible data source.

## 11. AI component contracts

### 11.1 Triage and investigation planning

Human analogue: a support representative identifies the issue and decides which
systems to inspect.

Input:

```json
{
  "case_id": "CASE-4928",
  "customer_id": "CUS-102",
  "complaint": "I was charged $80 even though the stylist cancelled.",
  "provided_references": {
    "appointment_id": "APPT-882"
  }
}
```

Output:

```json
{
  "category": "cancellation_fee_dispute",
  "summary": "Customer disputes a fee and claims the provider cancelled.",
  "entities": {
    "customer_id": "CUS-102",
    "appointment_id": "APPT-882"
  },
  "questions_to_answer": [
    "Was the fee captured?",
    "Who initiated the cancellation?",
    "Why was it cancelled?",
    "Which policy applied at the event time?"
  ],
  "required_evidence": [
    "appointment",
    "appointment_events",
    "payment",
    "cancellation_policy"
  ],
  "unsupported_case_type": false
}
```

The complaint is an allegation, not evidence. Triage must not treat customer wording
as proof of the event.

### 11.2 Investigation agent

Human analogue: opening customer, booking, audit, payment, and membership systems.

The agent receives an investigation plan and read-only tools. It returns facts with
provenance rather than only a prose summary.

Operational retrieval is deterministic and relational:

```text
Investigation Agent
        ↓ typed tool call
Operational service/repository
        ↓ parameterized SQL
PostgreSQL
        ↓ typed records
Investigation Agent
```

The model decides which bounded tool to call; it does not generate arbitrary SQL.
Exact identifiers, foreign keys, time ranges, and ledger queries are preferable to
semantic similarity for authoritative business data. Limited full-text or trigram
matching may assist a bounded service-name search, but a fuzzy match never proves
customer, appointment, or payment identity.

```json
{
  "facts": [
    {
      "fact_type": "cancellation_actor",
      "value": "employee",
      "source_type": "appointment_event",
      "source_id": "AEVT-883",
      "observed_at": "2026-08-21T14:32:00Z"
    },
    {
      "fact_type": "cancellation_fee_captured",
      "value": {
        "amount_cents": 8000,
        "currency": "USD",
        "payment_id": "PAY-992"
      },
      "source_type": "payment",
      "source_id": "PAY-992"
    }
  ],
  "missing_evidence": [],
  "conflicts": [],
  "tool_failures": []
}
```

### 11.3 Policy retrieval / Knowledge Agent

Human analogue: consulting the versioned internal handbook.

Policies use hybrid retrieval because they are versioned natural-language documents
rather than transactional records. The retrieval pipeline is:

```text
Policy question
    ↓
Hard metadata and applicability filters
    ├── effective date
    ├── location scope
    ├── service scope
    └── policy status/version
    ↓
Lexical PostgreSQL full-text search + semantic pgvector search
    ↓
Rank fusion
    ↓
Top candidate logical sections
    ↓
Fetch complete sections and linked definitions/exceptions
    ↓
Policy Agent applicability interpretation
```

Hard filters cannot be overridden by a high similarity score. Policy documents are
chunked on authored sections and subsections, not arbitrary fixed token windows.
Each section stores its policy ID, version, section ID, heading, body, parent,
effective dates, scope metadata, lexical search vector, and embedding.

The initial fusion method should be Reciprocal Rank Fusion so lexical and vector
scores do not require fragile direct normalization. Exact fusion parameters and
`top_k` remain tunable through retrieval evals.

Input:

```json
{
  "case_category": "cancellation_fee_dispute",
  "question": "Can a fee be retained when the provider cancelled?",
  "event_time": "2026-08-21T14:32:00Z",
  "location_id": "LOC-02",
  "service_type": "hair_color"
}
```

Output:

```json
{
  "applicable_policies": [
    {
      "policy_id": "POL-CANCEL",
      "version": 3,
      "section_id": "4.2",
      "title": "Provider-Initiated Cancellations",
      "rule": "Customers must not be charged a cancellation fee when the provider or business initiates the cancellation.",
      "effective_from": "2026-01-01",
      "effective_to": null
    }
  ],
  "applicability_status": "complete",
  "additional_evidence_requests": [],
  "policy_missing": false,
  "conflicting_policies": []
}
```

#### Bounded policy/evidence feedback loop

The initial operational investigation may be complete relative to the case plan but
still lack a fact introduced by a retrieved policy exception. This mirrors a human
support representative consulting the handbook and then returning to the business
system for one focused check.

The Policy Agent may return:

```json
{
  "applicability_status": "requires_additional_evidence",
  "applicable_policies": [
    {
      "policy_id": "POL-CANCEL",
      "version": 3,
      "section_id": "4.2",
      "rule": "Provider-initiated fees are refunded unless the appointment was transferred and fulfilled."
    }
  ],
  "additional_evidence_requests": [
    {
      "evidence_type": "appointment_transfer_history",
      "entity_id": "APPT-882",
      "question": "Was the appointment transferred and fulfilled?",
      "reason": "Policy section 4.2 contains a fulfilled-transfer exception.",
      "policy_citation": "POL-CANCEL-v3#4.2"
    }
  ]
}
```

The orchestrator validates each request against an evidence-type allowlist and a
mapping to known read tools. It then asks the Investigation Agent for only the new
facts, merges them into the persisted `EvidenceBundle`, and runs policy
applicability once more.

MVP loop limits:

- Maximum supplemental investigation rounds: 1
- Maximum new evidence requests in that round: 3
- Maximum supplemental operational tool calls: 4
- Reject repeated evidence requests
- Reject unknown evidence types
- Reject requests unrelated to a cited candidate policy
- Escalate if the fact remains unavailable or conflicting

The loop is a typed workflow edge, not a free-form conversation between agents.
The Policy Agent cannot call operational tools directly.

### 11.4 Resolution proposer

Human analogue: the case owner constructs a recommended outcome.

The proposer is constructive: given the complaint, evidence, and policy, what is the
best supported resolution?

Output:

```json
{
  "decision": "refund",
  "reason_code": "provider_initiated_cancellation",
  "action": {
    "type": "refund_payment",
    "payment_id": "PAY-992",
    "amount_cents": 8000,
    "currency": "USD"
  },
  "evidence_ids": ["APPT-882", "AEVT-883", "PAY-992"],
  "policy_citations": ["POL-CANCEL-v3#4.2"]
}
```

This is a proposal only. No mutation occurs.

### 11.5 Verifier

Human analogue: an independent supervisor attempts to find unsupported reasoning,
missing evidence, contradictions, incorrect policy application, or wrong action
arguments.

The verifier is adversarial rather than constructive. It receives the original
complaint, the proposal, the actual cited evidence records, applicable policy text,
and deterministic check results. It must not see only the proposer’s summary.

Passing output:

```json
{
  "verdict": "pass",
  "required_evidence_present": true,
  "policy_supports_decision": true,
  "amount_supported": true,
  "identity_consistent": true,
  "missing_evidence": [],
  "contradictions": [],
  "unsupported_claims": []
}
```

Failing output:

```json
{
  "verdict": "fail",
  "required_evidence_present": false,
  "policy_supports_decision": true,
  "amount_supported": false,
  "identity_consistent": true,
  "missing_evidence": [
    "No captured payment supports an $80 refund."
  ],
  "contradictions": [],
  "unsupported_claims": [
    "The proposal treats a payment authorization as captured money."
  ]
}
```

Verification adds value only if it is structurally independent:

- Different objective and instructions
- Strict pass/fail contract
- Actual source records, not proposal summary only
- Deterministic check results
- No action permissions
- Explicit missing-evidence and contradiction fields

If the verifier fails in the MVP, the case becomes
`HUMAN_INVESTIGATION_REQUIRED`. Do not implement an unlimited correction loop. A
single repair attempt may be considered later.

The verifier’s value will be evaluated using catch rate, false rejection rate,
latency, token cost, and unsafe-action reduction. It may be simplified if it does
not earn its cost.

### 11.6 Deterministic verification and disposition

LLM verification is not the safety boundary. Code must check:

```text
payment.customer_id == case.customer_id
payment.appointment_id == disputed appointment
payment.status == captured
refund_amount > 0
refund_amount <= remaining refundable amount
no completed refund already exists
all cited evidence IDs exist
policy was effective at event time
required evidence is complete
```

The deterministic disposition engine consumes the verified proposal and produces:

```text
AUTO_RESOLVED
HUMAN_APPROVAL_REQUIRED
HUMAN_INVESTIGATION_REQUIRED
```

No disposition is based solely on an LLM self-confidence score.

### 11.7 Grounded response writer

An optional bounded AI component may turn a verified outcome into a customer-safe
message. It cannot claim that a proposed action was executed.

For example, only after refund success:

```json
{
  "subject": "Your cancellation fee refund",
  "message": "We confirmed that your appointment was cancelled by the business and that an $80 cancellation fee was charged incorrectly. We have issued an $80 refund to the original payment method."
}
```

Internal employee IDs, model confidence, raw traces, and retrieval scores must not
be exposed to customers.

## 12. Resolution proposer versus verifier

This distinction is a deliberate design choice:

```text
Proposer: What should we do?
Verifier: Has the evidence and policy actually proved that we should do it?
```

Example failure the verifier should catch:

```json
{
  "payment_amount_cents": 8000,
  "status": "authorized",
  "captured_amount_cents": 0
}
```

A proposer may notice `$80` and recommend a refund. Verification must reject the
action because no money was captured.

Another subtle case:

```text
Event actor: employee
Event type: appointment_note_added
Note: "Customer called to cancel"
```

The employee recorded the event but did not initiate the cancellation. The system
must distinguish event author from cancellation actor.

## 13. ActionIntent and deterministic execution

Agents never directly call unrestricted mutation tools. A verified proposal becomes
an `ActionIntent`:

```json
{
  "action_intent_id": "ACT-019",
  "case_id": "CASE-4928",
  "action_type": "refund",
  "target_id": "PAY-992",
  "amount_cents": 8000,
  "currency": "USD",
  "reason_code": "provider_initiated_cancellation",
  "evidence_ids": ["APPT-882", "AEVT-883", "PAY-992"],
  "policy_citations": ["POL-CANCEL-v3#4.2"],
  "risk_tier": "approval_required",
  "status": "pending_approval",
  "idempotency_key": "CASE-4928:refund:PAY-992"
}
```

After approval, the executor reloads state and verifies it has not become stale:

- Target still exists and belongs to the same customer.
- Payment remains refundable.
- No other refund already completed.
- Approved amount matches the intent.
- Case was not already resolved.
- Idempotency key was not previously completed.

Execution output contains a deterministic receipt or a precise failure. Duplicate
execution should safely return `already_completed` rather than create a second
refund.

## 14. Escalation and approval rules

### Human investigation

Escalate when:

- Customer identity cannot be established.
- Required operational data is missing.
- Multiple possible appointments cannot be disambiguated.
- Operational records conflict.
- Applicable policy is unavailable or conflicting.
- The verifier finds an unsupported conclusion.
- A required tool repeatedly fails after bounded retries.
- The issue type is unsupported.
- The case is sensitive or high risk beyond the implemented domain.

Every escalation should contain:

- A machine-readable reason code
- A human-readable explanation
- Missing or conflicting evidence
- The concrete next investigation step where known

### Human approval

Require approval when:

- The action mutates financial or customer entitlement state.
- The action exceeds a configured threshold.
- The operation is otherwise categorized as sensitive.

The demo has one operations account with all company-side permissions. A production
version would integrate with enterprise identity and implement role/attribute-based
rules for locations, assignments, refund limits, and administrative actions.

Even in the one-account demo:

- Investigation agents receive read-only tools.
- Proposal and verifier components receive no mutation tools.
- Only the deterministic executor has narrow write capabilities.

## 15. Initial case families and paths

Prioritize depth over supporting many categories.

### 15.1 Cancellation-fee dispute

Possible variants:

- Business/provider cancelled: refund recommended.
- Customer cancelled within free window: refund/waive according to policy.
- Customer cancelled outside free window: fee upheld.
- No-show: apply no-show policy.
- Cancellation actor is ambiguous: human investigation.
- Payment was authorized but not captured: no refund action.
- Payment missing: human investigation.
- Policy missing or temporally inapplicable: human investigation.

### 15.2 Duplicate payment

Evidence may include payments, invoice obligation, appointment association, amount,
currency, capture state, and timing. A refund requires approval and idempotent
execution.

### 15.3 Membership-credit dispute

Evidence includes membership plan, immutable credit ledger, appointment attendance,
and prior adjustments. Corrections append compensating ledger entries rather than
silently overwriting a balance.

### 15.4 Online booking unavailable

Evidence includes employee schedule, employee-service qualification, location,
service availability, booking configuration, and business hours. Clear explanations
may be auto-resolved because they are read-only.

### Additional/deferred breadth

- Missing appointment or booking recovery
- Package usage and expiration
- Other unsupported or high-risk cases used to test escalation

Ambiguous/insufficient evidence is a property of every case family, not necessarily
a separate business category.

### Canonical paths

```text
Clear read-only explanation
  → verification passes
  → AUTO_RESOLVED

Supported financial correction
  → verification passes
  → HUMAN_APPROVAL_REQUIRED
  → revalidate
  → execute
  → RESOLVED

Supported fee denial
  → verification passes
  → auto-resolve or approval depending on final business policy

Missing or conflicting evidence
  → HUMAN_INVESTIGATION_REQUIRED

Unsupported/high-risk issue
  → HUMAN_INVESTIGATION_REQUIRED

Transient tool failure
  → bounded retry
  → continue on success
  → technical escalation/failure after retry limit

State changes while approval is pending
  → executor reloads state
  → return already completed or reject stale action safely
```

## 16. Multi-agent orchestration and bounded feedback

The MVP implements the multi-agent architecture first. A deterministic workflow
orchestrator owns phase order, persistence, retry behavior, and terminal decisions.
It is application code, not another AI agent.

The four logical agents are:

1. Case Manager Agent, invoked for initial planning and later for proposal synthesis
2. Investigation Agent, with operational read tools only
3. Policy Agent, with policy search/fetch tools only
4. Verifier Agent, with no mutation capability

```text
Workflow worker
    ↓
Case Manager: plan
    ↓ persist validated CasePlan
Investigation Agent
    ↓ persist validated EvidenceBundle
Policy Agent
    ├── policy applicability complete
    │       ↓
    └── additional policy-dependent fact required
            ↓
        validate request
            ↓
        supplemental Investigation Agent run (maximum one)
            ↓
        merge evidence and re-evaluate policy once
    ↓ persist validated PolicyBundle
Case Manager: propose
    ↓ persist ResolutionProposal
Deterministic pre-verification
    ↓
Verifier Agent
    ↓ persist VerificationResult
Deterministic disposition and execution
```

These are typed workflow transitions rather than conversational handoffs. Each
artifact is schema-validated and persisted before the next phase. An agent receives
only the minimum required case data and validated artifacts, not every preceding
agent's raw transcript.

At the inter-agent level the workflow is mostly sequential because policy selection
depends on discovered operational facts and proposal synthesis depends on both. The
bounded policy/evidence edge is the only cross-agent feedback loop in the MVP.

Allowed loops are:

- Bounded Investigation Agent to operational-tool loop
- Bounded Policy Agent to retrieval-tool loop
- One Policy Agent to supplemental Investigation Agent evidence-gap loop
- Retry of the current failed stage for classified transient failures

Disallowed MVP loops are:

- Unlimited Case Manager and Verifier debate
- Repeated Investigation and Policy Agent conversation
- Full-workflow restart after a retryable failure in a later completed phase

A Verifier failure produces `HUMAN_INVESTIGATION_REQUIRED`; it is not automatically
returned to the proposer for rationalization or rewriting.

### Future single-resolver baseline

Preserve a strategy boundary so a baseline can be added after the primary system is
reliable:

```python
class ResolutionStrategy(Protocol):
    async def resolve(self, case_id: str) -> ResolutionProposal:
        ...
```

The future baseline would share the frozen database, tools, policies, output
schemas, deterministic guards, verifier, disposition logic, executor, and evals.
Because the verifier is shared, it would more precisely be a **single resolver
baseline**, not a system with only one model call. Its implementation and formal
architecture comparison are deferred, not removed from future scope.

## 17. Evaluation design

Create approximately 50–60 strong eval cases after freezing business data. Use
known ground truth linked to a dataset version.

Example:

```json
{
  "case_id": "EVAL-019",
  "dataset_version": "luma_business_v1",
  "complaint": "I was charged even though the stylist cancelled.",
  "expected_category": "cancellation_fee_dispute",
  "required_evidence": [
    "appointment",
    "appointment_history",
    "payment",
    "cancellation_policy"
  ],
  "expected_policy_citations": ["POL-CANCEL-v3#4.2"],
  "expected_resolution": "refund",
  "expected_amount_cents": 8000,
  "expected_disposition": "human_approval",
  "should_escalate": false
}
```

### Eval families

1. Happy paths
2. Boundary and missing-data cases
3. Counterfactual pairs
4. Adversarial and operational-failure cases

Counterfactual example:

```text
A: provider cancelled; all other facts held constant → refund
B: customer cancelled after cutoff; all other facts held constant → uphold fee
```

### Grader hierarchy

Use deterministic graders wherever an exact answer exists:

- Category
- Resolution/action type
- Amount and currency
- Disposition
- Evidence IDs/types
- Policy version and section
- Tool arguments
- Forbidden actions
- Database postconditions
- Idempotency behavior

Use trace graders for:

- Required tools called
- Forbidden tools not called
- Correct record identifiers
- Evidence path completeness
- Retry and stopping behavior

Use model-based graders only where semantic judgment is genuinely needed:

- Explanation groundedness
- Whether wording overstates evidence
- Customer-response quality

### Metrics

- Case-classification accuracy
- Resolution accuracy
- Tool-selection accuracy
- Tool-argument accuracy
- Evidence completeness
- Policy retrieval recall
- Policy-section retrieval recall@k and applicable-policy accuracy
- Supplemental evidence-request precision and completion rate
- Incremental accuracy gained from the evidence-gap loop
- Redundant supplemental tool-call rate
- Groundedness
- Escalation precision and recall
- Incorrect auto-resolution rate
- Unsafe/unauthorized action rate, targeted at 0%
- Verifier catch rate and false rejection rate
- Average and P95 tool calls
- Average and P95 latency
- Tokens and estimated cost per case
- Retry rate and terminal failure rate

False auto-resolution should receive a larger penalty than unnecessary escalation.
Do not reduce the entire experiment to one accuracy number.

### Fairness controls

- Same model family unless model choice is explicitly the experiment
- Same dataset snapshot
- Same tools and policy corpus
- Same outcome schema
- Comparable budgets
- Multiple runs where nondeterminism is material
- Report variance or confidence intervals where feasible
- Separate quality, safety, latency, and cost results

## 18. Observability and audit

Treat four record types separately:

### Application logs

- Exceptions
- Retries
- Job claims and lease expiry
- API failures
- Worker lifecycle

### Metrics

- Case volume and queue depth
- Resolution and escalation rates
- Latency percentiles
- Tool and model failures
- Tokens and cost

### Distributed/agent traces

- Model generations
- Agent boundaries
- Tool calls and arguments
- Retrieval operations
- Guardrail and approval events
- Custom workflow spans

### Business audit log

- What was proposed
- Evidence and policy supporting it
- Who approved or rejected it
- What was executed
- Previous and new business state
- Idempotency and external/mock receipt

The business audit trail must remain available even if model tracing is disabled.
Trace payloads require a PII/redaction policy.

Employees see a simplified operational activity timeline. Builders see detailed
agent traces and eval artifacts outside the employee product.

## 19. User interfaces

### 19.1 Manual complaint intake

A small customer-like form can collect:

- Customer identity/reference
- Complaint text
- Optional appointment/payment reference
- Submission timestamp/source

It is an intake surface, not the main product.

### 19.2 Company operations product

The implemented demo uses one operations account with full company-side access.

Suggested pages:

1. Operations overview
2. Case queue
3. Case detail
4. Pending actions/approvals
5. Escalated cases

Operations overview metrics:

- Open cases
- Currently processing
- Auto-resolved
- Pending approval
- Human investigation required
- Average/oldest case age
- Cases by business category

Use **auto-resolved**, not **auto-approved**. Automatically handled cases never
entered a human approval gate.

The case-detail view should show:

- Original complaint
- Operational timeline
- Investigation checklist
- Evidence with clickable/source identifiers
- Applicable policy version and section
- Proposed resolution
- Verification results
- Current disposition
- Approval/reject/escalate controls where relevant
- Customer-safe response
- Simplified workflow activity
- Audit history

Escalations must show exactly what is missing or conflicting and, where known, what
the human should investigate next.

### 19.3 What is not in the employee UI

The following are builder/engineering artifacts and do not belong in the fictional
company product:

- Single versus multi-agent comparison
- Resolution-accuracy eval results
- Escalation precision/recall eval results
- Policy retrieval recall
- Eval datasets and prompt/model version comparisons
- Raw token and model-cost experiments
- Full low-level model traces

These belong in a separate evaluation/reporting workflow such as:

```text
evals/
├── datasets/
├── graders/
├── experiments/
├── runner.py
└── reports/
```

They may be shown by the project builder during an interview but are not accessible
as company-employee pages.

## 20. Prototype and production distinctions

### Initial/local implementation

```text
Manual form ─┐
             ├─→ FastAPI → PostgreSQL → resolution worker
Simulator ───┘                         ↓
                                  operations UI
```

The first queue may be PostgreSQL-backed. Workers can claim jobs using an atomic
lease/locking design. This avoids adding Redis or Kafka before scale requires it.

### Production discussion

A larger deployment might use:

- Managed PostgreSQL with backups and recovery
- Dedicated durable queue/workflow engine
- Stateless resolution workers
- Enterprise identity integration
- Tenant and location-level access control
- Payment and booking service adapters
- Secrets management
- PII controls and retention policies
- SLOs, alerting, and dead-letter operations

Online hosting is deliberately postponed until the core workflow, data integrity,
and evals are stable.

## 21. Guardrails and operational limits

Required controls include:

- Input schema validation
- Trusted identity context where available
- Read/write separation
- Narrow, typed tool contracts
- Agent tool-call and turn limits
- Model and tool timeouts
- Bounded retries with retryability classification
- Action approval policies
- Amount and currency validation
- Foreign-key and ownership validation
- Idempotency keys
- Revalidation immediately before execution
- Evidence citations in internal conclusions
- Customer-safe output grounding
- No safety decision based solely on self-reported confidence

## 22. Provisional implementation priority

The currently favored order is:

1. Business specification and policies
2. PostgreSQL schema, migrations, and integrity constraints
3. Reproducible connected data generator
4. Data validation and frozen `luma_business_v1`
5. Case-resolvability matrix
6. Safe read-only tools
7. Multi-agent workflow orchestrator and typed intermediate contracts
8. Case Manager planning plus Investigation Agent
9. Hybrid policy retrieval, Policy Agent, and bounded evidence-gap loop
10. Case Manager proposal, deterministic checks, and Verifier Agent
11. Disposition, action intents, approval, revalidation, and executor
12. Eval dataset and multi-agent quality/safety evaluation
13. Operations interface
14. Standalone ticket simulator
15. Single-resolver baseline and comparison, if time remains
16. Deployment, if still valuable

Priority principle:

```text
data integrity and working investigation
  > correct ground-truth evals
  > safety and idempotency
  > observable traces
  > dashboard completeness
  > visual polish
  > additional infrastructure or agents
```

## 23. Open design questions

These are intentionally unresolved and should be discussed before implementation
locks them in:

- Exact four-to-six MVP case categories
- Whether supported monetary denials may auto-resolve or always require review
- What non-financial actions, if any, may auto-execute
- Whether the semantic verifier runs for every case or only selected risk tiers
- Exact lexical/vector fusion parameters, retrieval `top_k`, and reranking needs
- Exact tool granularity and return contracts
- Which model(s) and reasoning settings to compare
- How to cap context, tool calls, retries, and total case cost
- Exact operations UI framework
- How processing jobs are leased and recovered after worker crashes
- Whether response generation is part of the agent workflow or a later component
- How many canonical hand-authored records versus general background records the
  synthetic dataset should contain
- The concrete acceptance criteria for `luma_business_v1`
- What engineering trace data should be stored locally versus only in an external
  tracing system

## 24. Decision log

### D-001: PostgreSQL is the authoritative database

**Status:** Accepted

**Rationale:** The domain is relationship-heavy and benefits from transactions,
constraints, locking, JSONB, reporting, and optional vector support.

### D-002: Business-data-first sequencing

**Status:** Accepted

**Rationale:** The resolution engine should be demonstrably designed over a frozen
organizational data contract rather than co-designing convenient answer-bearing
records with each agent case.

### D-003: Manual and simulated producers share the case API

**Status:** Accepted

**Rationale:** One ingestion contract reflects how additional real channels would
integrate and prevents the simulator from bypassing validation or persistence.

### D-004: Simulator is separate from the dashboard

**Status:** Accepted

**Rationale:** It is development/demo infrastructure, not a fictional employee
product feature.

### D-005: One operations account in MVP

**Status:** Accepted

**Rationale:** Full enterprise IAM is not central to the interview thesis. Internal
agent/executor capability separation remains required.

### D-006: No customer follow-up loop in MVP

**Status:** Accepted

**Rationale:** Multi-turn customer communication adds workflow complexity outside
the current core. Insufficient information escalates to human investigation.

### D-007: Engineering evals remain outside employee UI

**Status:** Accepted

**Rationale:** Employees need operational case information, while architecture and
quality experiments belong to the builder/engineering surface.

### D-008: Proposal and verification are separate responsibilities

**Status:** Accepted, subject to empirical validation

**Rationale:** Constructing a resolution and attempting to falsify it are different
objectives. Deterministic checks remain the safety boundary, and verifier value must
be measured.

### D-009: Implement multi-agent first and defer the single-resolver baseline

**Status:** Accepted

**Rationale:** The primary deliverable should be one complete, defensible system.
The strategy boundary remains compatible with a later baseline, which will share
data, tools, guards, outputs, and evals if time permits.

### D-010: Hosting is postponed

**Status:** Accepted

**Rationale:** Deployment is useful but should not precede the core data, workflow,
safety, and evaluation work.

### D-011: Use deterministic relational retrieval for operational evidence

**Status:** Accepted

**Rationale:** Customer, appointment, payment, membership, schedule, and audit truth
depends on exact identifiers, joins, time ranges, and ledgers. Agents select narrow
typed tools backed by parameterized SQL; they do not receive arbitrary SQL or use
embedding similarity to establish authoritative identity or financial facts.

### D-012: Use hybrid RAG for policy retrieval

**Status:** Accepted

**Rationale:** Versioned policy language benefits from both exact terminology and
semantic paraphrase matching. Hard temporal/scope filters run before PostgreSQL
full-text and pgvector retrieval, results are rank-fused, and complete logical
sections are passed to the Policy Agent for applicability interpretation.

### D-013: Allow one bounded policy/evidence feedback loop

**Status:** Accepted

**Rationale:** A retrieved policy may introduce an exception whose required fact was
not predictable during initial investigation. The Policy Agent may request one
allowlisted supplemental evidence round; unresolved gaps or conflicts then escalate.
No general agent debate loop is permitted.

### D-014: Use LangGraph as the sole agent-workflow orchestrator

**Status:** Accepted

**Rationale:** The system is an explicit stateful graph containing deterministic
nodes, tool-using agent nodes, conditional edges, one bounded loop, persistence, and
a human-approval pause. LangChain is used selectively for model/tool integrations,
while a second overlapping agent runtime is avoided.

### D-015: Use SQLAlchemy over Psycopg for application data access

**Status:** Accepted

**Rationale:** Psycopg is the low-level PostgreSQL driver; SQLAlchemy is the
higher-level query, mapping, session, and transaction layer that uses that driver.
The project benefits from SQLAlchemy across its related tables while retaining the
ability to execute explicit PostgreSQL-specific SQL for retrieval, locking, and
performance-sensitive operations. Alembic owns schema migrations.

### D-016: Keep all MVP persistence in one PostgreSQL system

**Status:** Accepted

**Rationale:** Operational data, case workflow, AI artifacts, policy text/vectors,
processing jobs, LangGraph checkpoints, and isolated eval truth use separate schemas
or tables inside one PostgreSQL database. pgvector and full-text search are database
capabilities, not separate datastores.
