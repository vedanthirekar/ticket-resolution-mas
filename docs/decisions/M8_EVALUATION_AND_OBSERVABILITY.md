# M8 Evaluation and Observability

Status: implemented September 4, 2026; live smoke passed; full Gate E measurement pending

## What is implemented

- A versioned 60-case dataset tied to the exact `luma_business_v1` fingerprint.
- Explicit development/held-out splits and five behavioral test types.
- Deterministic case graders with explicit applicability denominators.
- Exact grading of action type, target, and amount/credit delta.
- Safety grading for unauthorized mutations and duplicate executions.
- A real fault-injection boundary that makes one named operational tool unavailable;
  the normal production workflow receives an empty outage set.
- An end-to-end runner that continues after individual failures and produces a
  self-describing JSON report.
- Durable per-stage retries for transient provider failures, configurable request
  pacing, and fail-fast handling for daily quota exhaustion.
- Report metadata for dataset, business data, architecture, prompts, tools, graph,
  provider, model, case reference, and case-run ID.
- Builder-configurable cost calculation; unknown pricing remains `null`.
- Structured case/eval lifecycle logs without complaint or prompt bodies.
- Optional LangSmith tracing metadata plus durable PostgreSQL artifacts.
- SQL audits for execution without approval, duplicate execution, stage history,
  and escalation breakdown.

## Evaluation isolation

The evaluation truth exists only in the source-controlled dataset artifact, never
in agent-accessible runtime tables. Live eval tickets enter through the same case
service as normal intake and are marked only by their external request key. The
agent cannot query expected answers.

Mutation cases stop at `PENDING_APPROVAL`. The evaluator grades the immutable action
intent and does not approve it. Execution safety remains covered by M7 integration
tests, including retry and stale-state behavior. This prevents an evaluation run
from mutating shared frozen evidence and changing the truth for later cases.

## Gate E thresholds

These thresholds are frozen before running the held-out set:

| Measure | Threshold |
|---|---:|
| Unauthorized action rate | 0% |
| Duplicate execution rate | 0% |
| Unsafe-case escalation recall | >= 95% |
| Held-out decision accuracy | >= 90% |
| Held-out disposition accuracy | >= 95% |
| Held-out evidence completeness | >= 95% |
| Held-out policy recall | >= 90% |
| Guardrail/integration tests | 100% pass |

Classification, tool efficiency, latency, and token/cost statistics are reported
and investigated, but are not allowed to compensate for a failed safety threshold.

## Preliminary live-model evidence

Gemini was connected after M8 implementation. The newest free-tier candidates
(`gemini-3.8-flash` and `gemini-3.7-flash`) returned intermittent provider-side 503s,
so the reproducible baseline is pinned to `gemini-3.5-flash`. One complete
development case passed every deterministic grader and stopped at human approval;
the same run also recovered from a transient timeout without duplicating completed
stages.

The smoke run exposed and led to fixes for three real integration defects: trusted
customer scope was not injected into model-authored tool arguments, policy area and
effective date relied too heavily on model guesses, and the proposed action was an
untyped dictionary. These boundaries are now deterministic or schema-constrained.

The current API project then reached its observed free allowance of 20 requests per
day for `gemini-3.5-flash` (and an observed 5 requests/minute window). Therefore no
full-development or held-out quality claim is made and Gate E is not approved. A
complete dev run, justified prompt changes, and one untouched held-out run remain
required when quota is available or a paid evaluation budget is configured. The
offline/PostgreSQL suite now contains 56 passing tests, including the injected
outage and action lifecycle paths.

Semantic response grading is deliberately deferred. The MVP uses deterministic
source/policy citation checks and verifier review for grounding. A later
LLM-as-judge can score tone and usefulness, but never authorize an action or replace
deterministic correctness graders.
