# Luma evaluation system

This directory is builder-facing infrastructure. It is intentionally not exposed
in the operations dashboard.

## Dataset

`datasets/luma_cases_v1.json` expands to 60 cases anchored to the immutable
`luma_business_v1` fingerprint. It contains 36 development and 24 held-out cases
across happy-path, boundary, counterfactual, adversarial, and injected tool-failure
tests. Each example declares required operational sources, policy sections, tools,
disposition, outcome, and exact action where applicable.

The compact scenario-template format avoids pretending that paraphrases are 60
independent operational incidents. They are 60 language/behavior tests over 12
frozen ground-truth situations.

Validate the file without a database or model call:

```powershell
uv run luma-eval
uv run luma-eval --split held_out
```

Run a small live-model development experiment:

```powershell
uv run luma-eval --live --split development --limit 1
```

For a free-tier project limited to five requests per minute, set
`LUMA_MODEL_MIN_REQUEST_INTERVAL_SECONDS=13`. A case normally makes three to five
model calls, so check the model's requests-per-day quota before selecting a larger
slice. The runner retries transient failures from the last durable stage, but stops
the experiment on daily quota exhaustion and marks the report incomplete.

Run the held-out set only after prompts and thresholds are frozen:

```powershell
uv run luma-eval --live --split held_out
```

Live runs create ordinary `source=api` cases with `eval:` request keys and stop at
the approval interrupt. They never auto-approve or execute mutations. Generated
reports are written under `reports/generated/` and are ignored by Git; export the
chosen final report separately if it is to be reviewed or committed.

## Metrics and interpretation

Deterministic graders are authoritative for classification, outcome, disposition,
evidence/source/policy recall, expected tool use, exact action arguments,
escalation, unauthorized mutation, and duplicate execution. `null` means a metric
was not applicable or could not be priced; it is never silently treated as zero or
one.

Customer-response prose is not currently given an LLM-as-judge score. Grounding is
enforced structurally through source references and pre-verification. A semantic
grader can be added later for tone/helpfulness, but it must not override safety or
business-correctness grades.

## Tracing and privacy

LangGraph invocations include stable run names, architecture tags, case reference,
and case-run ID. Optional LangSmith export can be enabled with
`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`. The PostgreSQL
artifacts and exported JSON report remain the reproducible source of truth.

Only synthetic Luma data may be sent to an external trace/model provider. Logs do
not include complaint text or prompts. A real deployment would add field-level
redaction, retention controls, regional routing, and access policies before tracing
production traffic.
