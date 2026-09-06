# M7 Verification and Action Safety

Status: Implemented on September 4, 2026; action pre-verification revised September 5, 2026

## Purpose

M7 turns an M6 proposal into either a verified read-only resolution, a durable
approval request, or a precise human-investigation escalation. The language model
never owns the final safety boundary and never directly receives a write tool.

## Control flow

```text
Grounded M6 proposal
        |
        v
Deterministic pre-verification --fail--> Human investigation
        |
        v
Adversarial Verifier Agent (one call, actual source records)
        |
        +-- unsupported/missing/conflicting --> Human investigation
        |
        v
Deterministic disposition
        |
        +-- explanation only --> deterministic customer-safe response --> Resolved
        |
        `-- mutation --> immutable ActionIntent --> LangGraph interrupt
                                                   |
                              authenticated approve/reject record
                                                   |
                                             graph resume
                                                   |
                     reject --> Human investigation
                     approve --> re-read and compare business state
                                      |                 |
                                    stale             unchanged
                                      |                 |
                            Human investigation   idempotent execution
                                                        |
                                                receipt + Resolved
```

There is no verifier/case-manager debate loop. A verifier failure terminates the
automated path because repeated model discussion would increase cost without
creating new authoritative evidence.

## Responsibility boundaries

| Component | Responsibility | Cannot do |
|---|---|---|
| Deterministic pre-verifier | Validate citations, action schema, policy applicability, reliable action evidence, and target/value binding in one source record | Interpret business meaning |
| Verifier Agent | Independently challenge semantic support using the complaint, full operational source records, retrieved policy, and proposal | Call tools, repair the proposal, or execute an action |
| Disposition node | Convert verified state into `auto_resolve`, `human_approval`, or `human_investigation` | Accept model self-confidence as authority |
| Action-intent service | Bind one exact command to one target, before-state snapshot, stable hash, and idempotency key | Alter a command after approval |
| Approval service | Store one authenticated operations decision and rationale | Execute the mutation |
| Action executor | Re-lock the target, compare current and approved before-state, execute once, and return a receipt | Proceed when approval is missing or state is stale |

All MVP mutations require approval. `refund_payment` requires a customer-owned
payment reference, exact positive amount, and reason. `adjust_membership_credit`
requires a customer-owned membership reference, non-zero delta, and reason.

## Durability and idempotency

- An action has the stable key `case-run:{case_run_id}:action:1`.
- Reusing that key for a different command fails.
- Approval is a separate one-to-one record containing account, decision, rationale,
  and timestamp.
- The LangGraph interrupt exposes only the case and action-intent references. The
  durable database decision, not the resume payload, is authoritative.
- Re-running the CLI after a decision resumes an interrupted checkpoint.
- A succeeded execution returns its stored receipt on retry and does not create a
  second business mutation or execution attempt.
- Refund execution writes the refund, payment projection, payment event, execution
  attempt, case event, and receipt transactionally.
- Membership correction is append-only in `business.membership_ledger` and carries
  the approval and idempotency references.

## Fail-closed behavior

- Malformed, unsupported, uncited, cross-customer, excessive, or unreliably evidenced actions
  escalate.
- Verifier rejection creates no action intent.
- Operations rejection creates no execution attempt.
- A target state change after the approval request marks execution failed and moves
  the case from pending approval to human investigation.
- LLM output cannot bypass ownership, amount, approval, stale-state, or idempotency
  checks.

## Operations API

- `GET /api/actions/pending` lists exact pending commands for the authenticated
  operations account.
- `POST /api/actions/{action_reference}/decision` records an approve/reject decision
  and rationale.
- The case worker/CLI resumes the durable graph after the decision. The HTTP request
  does not execute financial or membership changes inline.

## Verification evidence

- PostgreSQL integration tests cover approval interrupt/resume, exact refund
  execution, repeat execution, append-only membership adjustment, verifier
  rejection, operator rejection, and state-change-after-approval failure.
- The full repository suite passes: **49 tests**.
- Ruff formatting/lint and strict mypy pass.
- No external model API is called by the suite; structured model doubles exercise
  the exact production contracts and graph routes.

M7 establishes deterministic safety behavior. M8 must still measure verifier catch
rate, false rejection, end-to-end decision quality, policy/evidence metrics,
latency, tokens, and cost before Gate E can be reviewed.
