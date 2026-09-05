# M10 Hardening and Presentation Review

Status: **Implemented on September 4, 2026**

M10 closes the product-hardening milestone without claiming that the deferred
agent-routing quality work or Gate E model validation is complete.

## Acceptance evidence

| Requirement | Evidence | Status |
|---|---|---|
| Clean local setup and demo path | Root README and `docs/DEMO_RUNBOOK.md` | Implemented |
| Reliable reset and reseed | Guarded `scripts/reset-demo.ps1`, scoped to this Compose project | Implemented; destructive execution remains operator-initiated |
| Architecture and sequence diagrams | Source-controlled Mermaid in `docs/ARCHITECTURE.md` | Implemented |
| Failure modes, threats, and production delta | `docs/PRODUCTION_READINESS.md` | Implemented |
| PII and trace policy | Explicit allowed/forbidden fields and production extensions | Implemented |
| Prompt/model/tool/graph change discipline | Versioned eval metadata and frozen development/held-out process | Implemented |
| Deterministic fallback | Real graph/action integration test plus versioned simulator fixtures | Implemented |
| CI | Migrations, deterministic generation, retrieval eval, dataset eval, all non-live Python tests, typing/lint, and web lint/build | Implemented |
| Eval report and error analysis | `docs/EVALUATION_REPORT.md`, derived from real runner output | Implemented; Gate E remains open |
| Interview narrative | `docs/INTERVIEW_PRESENTATION.md` and five-minute runbook | Implemented |

## Verification snapshot

The final local M10 verification completed with:

- Ruff format and lint: pass.
- Strict mypy over 63 source files: pass.
- Offline 60-case eval dataset validation: pass.
- PostgreSQL retrieval eval: 16/17 recall@5 (94.12%), above the frozen 90% gate.
- Full PostgreSQL-backed pytest suite: 67 passed.
- Next.js TypeScript check and production build: pass.
- Reset script PowerShell syntax parse: pass. The destructive reset itself was not
  run against the existing local database.

## Explicit holds

- Routing, graph topology, prompts, node responsibilities, and handoff quality are
  frozen as the current functional first pass and are not accepted as optimized.
- Gate E remains open. No full development or untouched held-out model-quality
  result exists for the current configuration.
- Hosting and production cloud infrastructure remain intentionally out of scope.
