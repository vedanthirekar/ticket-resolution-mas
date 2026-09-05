# M6 Multi-Agent Workflow

Status: Implemented on September 4, 2026

## Purpose

M6 introduces the first model-driven layer over the approved M5 evidence
contracts. It does not execute business mutations. Its output is either a grounded
resolution proposal for M7 verification or an explicit human-investigation reason.

## Fixed information flow

```text
Case + established customer
        |
        v
Case Manager: typed investigation plan
        |
        v
Investigator: choose one read-only call
        |
        v
Execute tool --> observe provenanced result
        ^                    |
        +--- up to 8 calls --+
        |
        v
Deterministic evidence completeness/conflict gate --fail--> Human investigation
        |
        v
Policy Agent: filtered hybrid retrieval + typed assessment
        |
        +-- one allowlisted supplemental fact, at most once --+
        |                                                  |
        +<-------------------------------------------------+
        |
        v
Case Manager: typed resolution proposal
        |
        v
M7 verifier, disposition, approval, and action lifecycle
```

This is deliberately not an unconstrained conversation among agents. The investigator has a
bounded observe-and-act loop so a discovery call can supply the identifier used by a later detail
call. A second policy-triggered supplemental evidence branch is capped at one call. Both boundaries
prevent an expensive or non-terminating debate.

## Agent and deterministic responsibilities

| Component | Model judgment | Deterministic enforcement |
|---|---|---|
| Case Manager plan | Confirm/correct the customer category hint, form evidence objectives and policy question | Canonical category/evidence schema; complaint remains untrusted |
| Investigator | Choose the next tool after observing previous results; stop when evidence is complete | Tool allowlist, customer binding, eight-call cap, discovered-reference enforcement; arbitrary SQL and writes are impossible |
| Evidence gate | None | Category minimums cannot be weakened; missing or contradictory facts escalate |
| Policy Agent | Select retrieved rules and identify one rule-required extra fact | Effective date and scope filter before ranking; citations must be retrieved IDs |
| Case Manager proposal | Synthesize facts and rule into a proposed outcome | Unknown citations are rejected; every mutation must be `human_approval` |

The agent plan may add evidence requirements but cannot remove the deterministic
minimum for its selected category. Complaint text remains an allegation and never
satisfies an evidence requirement.

## Model boundary

`StructuredModel` is the provider-neutral application interface. Implemented
adapters support Google Gemini and OpenRouter's OpenAI-compatible endpoint. The
current default is `minimax/minimax-m3:free`, selected after the previous free provider became
unreliable under shared-pool throttling. Configuration rejects an OpenRouter model without the
`:free` suffix. Provider choice remains
isolated to the factory, so graph nodes and contracts do not change.

No external model call occurs in the default test suite. `ScriptedStructuredModel`
provides deterministic, schema-validated responses for trajectory, safety, and
recovery tests. A live provider run requires `LUMA_MODEL_API_KEY` and remains a
separate, cost-bearing test/demo action.

## Durability model

Two persistence layers have different jobs:

- LangGraph's PostgreSQL checkpointer stores graph state after each superstep. The
  `case_run_id` is the checkpoint `thread_id`.
- `ai_runtime.workflow_stages` and the existing artifact tables store application
  audit records. A completed stage is reused if execution crosses the database
  commit/checkpoint boundary, preventing duplicate plans, evidence, retrievals, or
  proposals.

Checkpoint tables are installed by the LangGraph package and intentionally remain
framework-owned; Alembic owns Luma application schemas. Checkpoint serialization
disables pickle fallback and permits no arbitrary MessagePack modules.

## Bounded execution

- Maximum operational calls per initial investigation: 8 by default.
- Maximum supplemental calls: 1.
- Model timeout: 30 seconds per structured call by default.
- Provider retries: 2 by default.
- Maximum model output: 2,000 tokens per call by default.
- There is no model-selection router and no verifier debate loop.
- Identity failure, unsupported category, missing/conflicting required evidence,
  absent policy, invalid supplemental evidence, and ungrounded citations all fail
  closed.

Input/output token counts are captured when the provider returns usage metadata and
stored on the completed case run. Cost calculation and full tracing belong to M8.

## Verification evidence

- Unit tests prove fixed category requirements cannot be weakened, an agent plan
  may extend them, contradictions fail closed, and mutations cannot auto-resolve.
- PostgreSQL integration tests execute the canonical provider-cancellation case through planning,
  iterative operational calls, hybrid retrieval, policy assessment, and a grounded human-approval
  proposal. A separate regression omits the appointment ID and proves discovery supplies the exact
  identifier used by later timeline and payment calls.
- A missing-identity case escalates without any model call.
- Calling a completed plan stage twice invokes the model once and persists one
  stage record.
- A process-boundary test fails at proposal, closes the first PostgreSQL
  checkpointer, creates a new workflow/checkpointer, and resumes at proposal
  without repeating planning, investigation, or policy retrieval.

## Deferred to M7

M6 proposals are not verified final decisions. M7 adds deterministic
pre-verification, the adversarial Verifier Agent, disposition rules, action intents,
approval interrupts, revalidation, idempotent execution, and grounded customer-safe
response generation.
