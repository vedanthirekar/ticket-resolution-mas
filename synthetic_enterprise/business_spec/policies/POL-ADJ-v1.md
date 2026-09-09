# Operational Adjustments and Approval Policy

| Metadata | Value |
|---|---|
| Policy ID | `POL-ADJ` |
| Version | `1` |
| Document type | Internal control policy |
| Policy owner | Director of Customer Operations |
| Approved by | Chief Operating Officer |
| Document classification | Internal |
| Intended audience | Customer Operations, Finance Operations, Location Leadership |
| Approved on | 2023-12-15 |
| Review cycle | Annual and upon material control change |
| Effective from | 2024-01-01 00:00 UTC |
| Effective through | Open-ended |
| Scope | Support-originated explanations and corrective actions |
| Supersedes | None |

## POL-ADJ-v1#1 Purpose

This policy establishes authorization, evidence, and audit requirements for
support-originated explanations and corrective actions. It separates routine
read-only case resolution from changes to financial, membership, appointment, or
configuration records.

## POL-ADJ-v1#2 Required action record

### POL-ADJ-v1#2.1 Corrective proposal

A corrective proposal identifies the customer, target record, action type, exact
amount or quantity when applicable, current state, intended state, reason, supporting
operational references, and governing policy sections.

## POL-ADJ-v1#3 Approval boundary

### POL-ADJ-v1#3.1 Explanation only

A grounded explanation that changes no business state may be completed without a
corrective transaction.

### POL-ADJ-v1#3.2 Mutating action

A refund, void, fee waiver, membership-ledger entry, appointment recovery, or
configuration change requires approval by an authenticated operations employee
with adjustment authority before execution.

Approval is specific to the proposed target and amount or quantity. Changing those
values invalidates the approval and requires a new proposal.

## POL-ADJ-v1#4 Execution safety

### POL-ADJ-v1#4.1 Idempotency

Every approved action has a stable idempotency key. Retrying the same action returns
its original result and must not create an additional refund, ledger entry, booking,
or configuration mutation.

### POL-ADJ-v1#4.2 Revalidation

Immediately before execution, Luma revalidates the target state and financial or
credit limit. If the state changed after approval, execution stops for review.

### POL-ADJ-v1#4.3 Audit

The approval identity, time, before-state, command, provider result, and after-state
are retained even if execution fails.

## POL-ADJ-v1#5 Investigation boundary

### POL-ADJ-v1#5.1 Unsupported action

No correction is executed when identity, target, amount/quantity, required evidence,
effective policy, or internal consistency is unresolved. The record is routed for
human investigation with the missing or contradictory facts named explicitly.

## POL-ADJ-v1#6 Roles and responsibilities

### POL-ADJ-v1#6.1 Case reviewer

The case reviewer confirms customer scope, gathers the required source records,
documents the proposed outcome, and must not approve their own unsupported change.

### POL-ADJ-v1#6.2 Approver

The approver verifies that the target, amount or quantity, evidence, governing
policy, and customer impact match the proposal. Approval is a business decision and
must not be inferred from an employee's ability to access the system.

### POL-ADJ-v1#6.3 System custodian

The system custodian maintains access controls, idempotent execution, audit
retention, and monitoring. The custodian does not determine whether an individual
customer adjustment is warranted.

## POL-ADJ-v1#7 Records and monitoring

### POL-ADJ-v1#7.1 Required records

Luma retains the case reference, proposal, cited source records, policy version,
approval or rejection, execution attempts, provider response, customer
communication, and resulting state under the corporate records-retention schedule.

### POL-ADJ-v1#7.2 Control review

Customer Operations reviews failed executions, repeated requests, approval-control
exceptions, and unusual adjustment patterns. Suspected fraud, access misuse, or a
material control failure is escalated through the incident-management process.

## POL-ADJ-v1#8 Related documents

### POL-ADJ-v1#8.1 Governing and supporting policies

This control is applied with the policy governing the underlying obligation,
including `POL-CAN`, `POL-PAY`, `POL-MEM`, or `POL-BOOK`. Those policies determine
whether a correction is warranted; this policy determines how the correction is
authorized and executed.

## POL-ADJ-v1#9 Document administration

### POL-ADJ-v1#9.1 Revision history

| Version | Approved on | Effective from | Change summary |
|---|---|---|---|
| 1 | 2023-12-15 | 2024-01-01 | Initial controlled policy for support-originated adjustments. |
