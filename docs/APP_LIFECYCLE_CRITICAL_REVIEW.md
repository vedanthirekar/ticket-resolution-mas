# End-to-End App Lifecycle Review

Status: reviewed September 5, 2026

## Executive assessment

Luma has a strong core as an evidence-grounded case recommendation and approval
engine. Its automated path is coherent: intake is durable, investigation uses
customer-scoped operational tools, policy is retrieved with temporal filters,
proposals are typed and cited, mutations require approval, and execution is
revalidated and idempotent.

It is not yet a complete real-world case-resolution product. Human investigation
now has a documented closure workflow, and resolved cases with a supplied contact
email now produce an employee-reviewed, mock-delivered final response. Live-model
quality and real business impact remain unproven.

Indicative maturity assessment:

| Area | Assessment |
|---|---:|
| Core product concept | 8/10 |
| Prototype safety architecture | 8/10 |
| Automated happy path | 7/10 |
| Employee operational workflow | 5/10 |
| Customer end-to-end experience | 5/10 |
| Production readiness | 3/10 |

## Lifecycle findings

| Stage | What works | Principal gap |
|---|---|---|
| Intake | Atomic case and job creation; source idempotency; contact email captured for the simulation | Claimed customer reference and supplied email are not authenticated; no attachments or channel integration |
| Queue | Durable PostgreSQL lease and retry behavior | No ownership, SLA, age-based prioritization, or dead-letter administration |
| Investigation | Bounded, narrow, customer-scoped operational tools | Some evidence contracts stop investigation before all decision facts are collected |
| Policy | Effective/scope filtering and section citations | Supplemental evidence does not currently trigger policy reassessment |
| Proposal | Typed outcome, citations, and action contract | Exact financial calculation is still substantially model-derived |
| Verification | Deterministic precheck plus independent verifier | Deterministic disposition does not enforce every verifier recommendation field |
| Approval | Durable decision, rationale, checkpoint resume | One global role; no separation of duties or risk thresholds |
| Execution | Ownership, stale-state, refundable-balance, and idempotency checks | Executor is a mock external integration |
| Human investigation | Records and policy can be researched; employees can acknowledge, document, and close escalations | Assignment, SLA, and richer collaboration remain absent |
| Customer resolution | A final email draft is prepared after genuine resolution, can be edited, and has an auditable mock-send action | Response quality is generic; real delivery and verified customer identity are deferred |
| Measurement | Basic counts and average resolution time | No handling-time, SLA, override, repeat-contact, quality, or ROI measurements |

## Highest-priority product gaps

### 1. Complete human investigation — MVP implemented

Employees need to acknowledge an escalation, record findings, see an actionable
reason, make a documented manual decision, close the escalation, and leave a
customer-safe response. Financial mutations must continue through the existing
approval and deterministic execution boundary rather than gaining a manual
bypass.

### 2. Deliver the final customer response — prototype implemented

The prototype deliberately does not ask customers for supplemental evidence or
run a conversational follow-up flow. Missing evidence escalates to an employee,
leaving any customer contact decision with the business. Manual intake captures a
contact email; after an automatic or human resolution, Luma prepares a deterministic
email draft from the finalized response and completed action receipt. An employee
can edit it and record an idempotent mock delivery. Real email delivery, account-
verified addresses, and appeal/reopen behavior remain future work.

### 3. Correct policy and verifier control-flow gaps

- Reassess policy after the one allowed supplemental evidence lookup.
- Require verifier outcome/disposition agreement and honor `requires_human`.
- Derive the material event date from the selected subject record rather than the
  first date found in a broad discovery result.
- Refine deterministic evidence requirements for missing-appointment and
  membership cases.

### 4. Produce useful grounded resolution communication

The customer response should concisely state what was found, the governing rule,
the decision, any completed action, timing expectations, and the next available
step. It must be derived from verified facts without exposing internal reasoning.

### 5. Surface the complete action audit trail

The employee case page should continue showing completed or rejected actions,
approver identity and rationale, execution attempts, receipts, and failures after
an item leaves the pending queue.

### 6. Add operational case management

Add assignment, escalation-specific work queues, SLA/due dates, oldest-case
visibility, internal collaboration, related-case detection, saved filters,
pagination, and dead-letter handling.

### 7. Validate model quality and business impact

Gate E remains open. Before claiming production value, measure live decision and
disposition accuracy, evidence completeness, policy recall, unsafe-action rate,
handling-time reduction, containment, approval turnaround, overrides, reopens,
customer satisfaction, and cost per resolved case. Compare against manual handling
and eventually a simpler single-resolver baseline.

## Product positioning

The most defensible initial positioning is:

> Luma resolves repetitive, evidence-heavy operational disputes by assembling the
> facts and applicable policy automatically, while keeping financial corrections
> under human control.

This is a stronger and more measurable promise than attempting to automate every
support ticket. Expansion into more categories should follow completion and
measurement of the current five-case-family workflow.

## Recommended implementation order

1. Human-investigation lifecycle — MVP complete
2. Final customer email drafting and mock delivery — prototype complete
3. Policy/verifier correctness fixes
4. Grounded customer-resolution writing
5. Complete approval/execution audit display
6. Assignment, SLA, escalation, and dead-letter operations
7. Full live-model and business-impact evaluation
8. Real integrations, IAM hardening, and additional case families
