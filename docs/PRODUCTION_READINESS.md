# Production Readiness and Threat Model

## What the prototype proves

- Durable, idempotent intake and PostgreSQL job leasing.
- Read-only investigation with trusted case/customer scoping injected outside the
  model.
- Effective-date and scope filters before hybrid policy ranking.
- Typed outputs at every probabilistic boundary.
- Deterministic evidence, disposition, authorization, amount, ownership,
  refundable-balance, stale-state, and idempotency checks.
- Durable human approval and crash-safe graph continuation.
- Auditable artifacts, structured logs, eval reports, and operational UI.

## Threats and controls

| Threat or failure | Implemented control | Production extension |
|---|---|---|
| Prompt injection in a complaint | Complaint is data; tools are fixed and scoped; writes are unavailable to investigation | Input threat classifier and red-team corpus |
| Cross-customer data access | Server injects the trusted customer reference and rejects conflicting model arguments | Tenant isolation/RLS and scoped service identities |
| Hallucinated fact or policy | Evidence/policy citations, structural pre-verifier, independent verifier | Calibrated adjudication sampling and drift alarms |
| Wrong policy version | Deterministic event date plus effective/scope filtering before ranking | Policy publication workflow and legal approval |
| Duplicate or oversized refund | Frozen action, approval, refundable balance, threshold, and idempotency checks | Payment-provider idempotency plus reconciliation |
| State changes after approval | Before-state snapshot is revalidated under row lock | External version tokens and saga compensation |
| Worker crash | Row lease, retries, checkpointing, idempotent stage artifacts | Lease heartbeat, autoscaling, dead-letter alerting |
| Provider outage or quota | Timeout/retry classification and eventual human escalation | Multi-region provider fallback and circuit breaker |
| Eval truth leaks into runtime | Separate files/schema role and operations-query exclusion | Separate accounts/projects and deployment pipeline |
| Sensitive data leaks to traces | Structured logs omit complaint/prompt text and secrets | Field-level redaction, retention limits, DLP review |
| Stolen employee session | HTTP-only, same-site cookie and server-side revocation | SSO/MFA, CSRF token, device/session policies |

## Known prototype limitations

- One operations account; no real IAM/RBAC or tenant isolation.
- The worker lease has no heartbeat. Configure the lease above worst-case model
  latency; add heartbeats before scaling slow workloads.
- SSE uses one-second PostgreSQL polling. Production should use LISTEN/NOTIFY or an
  event broker when concurrency warrants it.
- The customer identity reference is asserted at intake rather than authenticated.
  Identity verification and requests for more customer information are future work;
  unresolved identity escalates.
- The mock action executor is transactionally realistic but is not a real payment or
  booking integration.
- Full live-model Gate E metrics are pending provider quota. No quality claim should
  be made from the single smoke case.
- No hosting, backups, disaster recovery, secret manager, or infrastructure-as-code
  is implemented yet.

## PII and observability policy

Logs and trace metadata may contain case/run references, stage names, tool names,
latency, token counts, status, and error classes. They must not contain complaint
text, prompts, model responses, customer names/contact details, API/session tokens,
or complete payment data. Rich evidence remains access-controlled in PostgreSQL and
the operations workspace. A production retention policy should separately govern
operational records, security logs, and model traces.

## Change discipline

Any prompt, model, tool schema, retrieval configuration, policy corpus, graph, or
business dataset change gets a version identifier and a development eval run. The
held-out split runs only after selection is frozen. Release promotion requires zero
unauthorized actions, zero duplicate execution, passing guardrails, and documented
error analysis against Gate E thresholds.
