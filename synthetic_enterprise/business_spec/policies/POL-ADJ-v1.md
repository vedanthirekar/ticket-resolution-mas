# Operational Adjustments and Approval Policy

| Metadata | Value |
|---|---|
| Policy ID | `POL-ADJ` |
| Version | `1` |
| Effective from | 2024-01-01 00:00 UTC |
| Effective through | Open-ended |
| Scope | Support-originated explanations and corrective actions |
| Supersedes | None |

## POL-ADJ-v1#1 Purpose

This policy separates read-only explanations from actions that change financial,
membership, appointment, or configuration state.

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
before execution. The first implementation uses one operations account with this
authority.

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

