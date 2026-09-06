# Agentic Case Resolution Engine

An AI engineering project that investigates operational support
cases, applies business policy, proposes a grounded resolution, verifies it, and
either resolves safely or escalates for human review.

This repository is being delivered data-first. The authoritative record of the
product, data, agent, safety, evaluation, and observability decisions is:

- [PROJECT_DESIGN.md](PROJECT_DESIGN.md)

The staged delivery plan, including the detailed data-first implementation
checkpoint and the end-to-end roadmap, is:

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

The design is intentionally a living document. Decisions that are not yet locked
are marked as proposed or open rather than presented as settled implementation.

## Current implementation status

M0 through M8 and Gates A-D are complete. The approved, immutable
`luma_business_v1` operational dataset is the input contract for case resolution.
The model-free runtime now provides transactional intake, idempotency, durable
PostgreSQL job leases, case history, one-account operations sessions, and explicit
AI artifact storage. Typed operational evidence tools and independently evaluated
hybrid policy retrieval are implemented. The fixed LangGraph workflow now performs
typed planning, bounded investigation, deterministic evidence gating, policy
assessment, one optional supplemental lookup, and grounded proposal generation.
M7 adds deterministic pre-verification, an adversarial verifier, deterministic
disposition, durable approval interrupts, target-state revalidation, and
idempotent refund/membership execution. M8 adds a versioned 60-case dataset,
deterministic quality/safety graders, fault injection, exportable experiment
reports, trace metadata, structured logs, and audit queries. An earlier Gemini 3.5
Flash end-to-end smoke case passed, including transient retry recovery. The runtime
supports Anthropic, Gemini, and OpenRouter. The example configuration uses
`claude-sonnet-4-6`; configuration rejects paid OpenRouter model IDs. Gate E remains
pending until the complete development and untouched held-out runs finish, and no
aggregate model-quality numbers are fabricated.

M9 is implemented. The Next.js operations product includes authenticated overview,
queue, enriched case workspace, approval handling, and live SSE refresh. A durable
worker claims PostgreSQL jobs and resumes LangGraph after approval. Customer manual
intake and the standalone 10-20 second simulator both use the same API, while the
simulator, employee UI, and builder-only eval reports remain separate surfaces.
M10 is implemented with CI, source-controlled architecture and sequence diagrams,
a guarded demo reset/reseed path, deterministic fallback, a threat and
production-readiness review, an evaluation/error review, and an interview
presentation narrative. Full live-model Gate E remains open pending adequate
provider quota and the deferred routing, prompt, node, and handoff quality work.

The M1 business documents begin at:

- [synthetic_enterprise/business_spec/README.md](synthetic_enterprise/business_spec/README.md)
- [synthetic_enterprise/business_spec/GATE_A_REVIEW.md](synthetic_enterprise/business_spec/GATE_A_REVIEW.md)
- [synthetic_enterprise/business_spec/GATE_B_REVIEW.md](synthetic_enterprise/business_spec/GATE_B_REVIEW.md)
- [synthetic_enterprise/business_spec/CASE_RESOLVABILITY.md](synthetic_enterprise/business_spec/CASE_RESOLVABILITY.md)
- [synthetic_enterprise/business_spec/GATE_C_REVIEW.md](synthetic_enterprise/business_spec/GATE_C_REVIEW.md)
- [docs/decisions/CASE_RUNTIME_DESIGN.md](docs/decisions/CASE_RUNTIME_DESIGN.md)
- [docs/decisions/M4_RUNTIME_REVIEW.md](docs/decisions/M4_RUNTIME_REVIEW.md)
- [docs/decisions/M5_TOOLS_AND_RETRIEVAL.md](docs/decisions/M5_TOOLS_AND_RETRIEVAL.md)
- [docs/decisions/GATE_D_REVIEW.md](docs/decisions/GATE_D_REVIEW.md)
- [docs/decisions/M6_AGENT_WORKFLOW.md](docs/decisions/M6_AGENT_WORKFLOW.md)
- [docs/decisions/M7_VERIFICATION_AND_ACTION_SAFETY.md](docs/decisions/M7_VERIFICATION_AND_ACTION_SAFETY.md)
- [docs/decisions/M8_EVALUATION_AND_OBSERVABILITY.md](docs/decisions/M8_EVALUATION_AND_OBSERVABILITY.md)
- [docs/decisions/M9_OPERATIONS_UI.md](docs/decisions/M9_OPERATIONS_UI.md)
- [docs/decisions/M10_HARDENING_REVIEW.md](docs/decisions/M10_HARDENING_REVIEW.md)
- [evals/README.md](evals/README.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md)
- [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md)
- [docs/INTERVIEW_PRESENTATION.md](docs/INTERVIEW_PRESENTATION.md)
- [docs/EVALUATION_REPORT.md](docs/EVALUATION_REPORT.md)
- [synthetic_enterprise/data_generation/manifests/luma_business_v1.json](synthetic_enterprise/data_generation/manifests/luma_business_v1.json)

## Local development

Prerequisites:

- Python 3.12
- `uv`
- Docker Desktop with Docker Compose

Create local configuration:

```powershell
Copy-Item .env.example .env
```

Install the Python environment:

```powershell
uv sync --dev
```

Start PostgreSQL and apply migrations:

```powershell
docker compose up -d postgres
uv run alembic upgrade head
```

Generate and independently validate the frozen synthetic dataset:

```powershell
uv run luma-generate-enterprise
```

Create the single local operations account and start the API:

```powershell
uv run luma-bootstrap
uv run luma-api
```

Build or refresh the local policy-vector index:

```powershell
uv run luma-index-policies
uv run python evals/run_policy_retrieval.py
```

Manual intake and the standalone simulator use the same endpoint:

```http
POST /api/cases
{
  "complaint_text": "I was charged even though the provider cancelled.",
  "source": "manual",
  "external_request_key": "manual-demo-001",
  "claimed_customer_reference": "CUS-000102",
  "claimed_category": "cancellation_fee_dispute"
}
```

The employee-side API requires a bearer session obtained from `POST /api/auth/login`.
The Next.js BFF stores that token only in an HTTP-only cookie. Simulator controls
are intentionally absent from both the API and employee dashboard.

Verify database connectivity and the pgvector extension:

```powershell
uv run python -m luma.db.health
$env:RUN_DB_TESTS = "1"
uv run pytest -m integration
```

Run the default non-model checks:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -m "not integration and not live_model"
```

The default test command never invokes an external model API. Local credentials and
database volumes must not be committed.

Initialize LangGraph's PostgreSQL checkpoint tables once after applying Alembic
migrations:

```powershell
uv run luma-agent --setup-checkpoints
```

To run one ingested case with the configured live model adapter, set
`ANTHROPIC_API_KEY` for the default Anthropic provider (or `LUMA_MODEL_API_KEY`
for Gemini/OpenRouter) and use its public reference:

```powershell
uv run luma-agent CASE-XXXXXXXXXXXX
```

This command can incur provider cost. The normal test suite uses a deterministic
model double and never reads the key.

Run the product locally in separate terminals after bootstrapping PostgreSQL and
the LangGraph checkpoint tables:

```powershell
uv run luma-api
uv run luma-worker
Set-Location web
npm install
npm run dev
```

Open `http://localhost:3000/login` for operations or `/submit` for customer manual
intake. The frontend defaults to `http://127.0.0.1:8000`; set `LUMA_API_URL` for a
different backend.

Run the optional independent intake simulator until Ctrl+C:

```powershell
uv run luma-simulator
```

Use `--count 5` for a bounded demo. It selects tightly linked scenarios from
`simulator/tickets.jsonl` and waits a random 10-20 seconds between submissions.

Reset and deterministically reseed the local demo database when rehearsal state
must be removed:

```powershell
.\scripts\reset-demo.ps1 -ConfirmDestructiveReset
```

Validate the 60-case evaluation dataset without calling a model:

```powershell
uv run luma-eval
```

After selecting and configuring a model, run development cases before the held-out
split. Live evals may incur provider cost:

```powershell
uv run luma-eval --live --split development
uv run luma-eval --live --split held_out
```
