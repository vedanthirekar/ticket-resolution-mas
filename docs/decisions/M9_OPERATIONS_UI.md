# M9 Operations UI and Simulator

Status: implemented September 4, 2026

## Product boundary

The employee operations surface and ticket simulator are independent. The dashboard
contains no simulator controls, status, or implementation details. The standalone
simulator submits through the same intake API as manual cases.

Builder evaluation traffic is also excluded from the employee surface. Operations
queries reject cases whose external request key begins with `eval:`; evaluation
reports remain builder-only artifacts.

## Implemented system

- Authenticated `GET /api/operations/overview` provides operational status counts,
  active/pending/escalated totals, resolution rate, and average resolution time.
- Authenticated `GET /api/operations/cases` supports status, source,
  category, text/reference search, bounded pagination, and latest-run outcomes.
- `GET /api/operations/cases/{reference}` assembles the latest run, evidence,
  policy citations, proposal, verification, action lifecycle, escalations, case
  events, and simplified stages. It exposes no hidden chain-of-thought.
- `GET /api/operations/events` emits authenticated SSE invalidations. The UI
  refetches authoritative read models rather than treating stream messages as state.
- Approval or rejection atomically enqueues a per-action continuation job. A leased
  worker resumes the durable LangGraph checkpoint, revalidates current target state,
  and completes or escalates the action.
- `web/` is a Next.js/TypeScript product with an HTTP-only cookie BFF, overview,
  filterable queue, case workspace, and approval queue. `/submit` is a visually
  separate customer intake surface.
- `luma-simulator` is an independent standard-library Python process backed by
  `simulator/tickets.jsonl`; it submits every 10-20 seconds by default through the
  public intake API and stops with Ctrl+C.

The queue uses one PostgreSQL query rather than loading AI artifacts per row. It
selects the latest run with PostgreSQL `DISTINCT ON`, appropriate because PostgreSQL
is already the system-of-record contract. Detail reads favor clarity over minimizing
query count because they load one case and its bounded artifacts.

## Deliberate exclusions

- No model accuracy, eval history, architecture comparison, or token/cost page in
  the employee product.
- No simulator route, controls, or state in the dashboard.
- No role matrix in the prototype; one operations account has all permissions.
- No raw prompts, hidden reasoning, or chain-of-thought. The UI shows persisted
  evidence, policy, concise decision rationales, guardrail outcomes, and audit events.

Stopping or deleting the simulator leaves manual intake and operations behavior
unchanged. This preserves the product boundary discussed before implementation.
