# Membership Credit Policy

| Metadata | Value |
|---|---|
| Policy ID | `POL-MEM` |
| Version | `1` |
| Document type | Internal membership operations policy |
| Policy owner | Director of Membership Operations |
| Approved by | Chief Operating Officer |
| Document classification | Internal |
| Intended audience | Membership Operations, Customer Operations, Finance Operations |
| Approved on | 2023-12-15 |
| Review cycle | Annual and upon material membership-terms change |
| Effective from | 2024-01-01 00:00 UTC |
| Effective through | 2025-12-31 23:59:59 UTC |
| Scope | Essential, Plus, and Premier memberships |
| Superseded by | `POL-MEM` version 2 |

## POL-MEM-v1#1 Purpose

This policy establishes membership-credit grants, consumption, expiration,
settlement, and correction requirements before January 1, 2026.

## POL-MEM-v1#2 Plan grants

### POL-MEM-v1#2.1 Monthly entitlement

An active membership receives its plan's integer credit grant after successful
monthly renewal: Essential 1, Plus 2, and Premier 4.

### POL-MEM-v1#2.2 Pause and cancellation

Paused, cancelled, and expired memberships receive no future grant. Existing grants
retain their original expiration.

## POL-MEM-v1#3 Credit validity

### POL-MEM-v1#3.1 Consumption order

Eligible services consume the earliest-expiring available credits first.

### POL-MEM-v1#3.2 Expiration

Each grant expires 60 days after its grant timestamp. Expiration is recorded as an
immutable ledger entry and does not change when a membership is paused or cancelled.

## POL-MEM-v1#4 Appointment settlement

### POL-MEM-v1#4.1 Fulfilled service

A completed eligible service consumes the catalog credit cost quoted on its
appointment. Cash-only services and add-ons do not consume membership credits.

## POL-MEM-v1#5 Cancellation effects

### POL-MEM-v1#5.1 Provider or business cancellation

Credits consumed for an appointment not fulfilled because the provider or business
cancelled must be restored through a reversal or correction linked to the original
consumption.

### POL-MEM-v1#5.2 Customer late cancellation or no-show

When the effective cancellation policy allows a charge, Luma may retain the credits
allocated to the appointment instead of collecting the cash fee, up to the booked
service's credit cost. The settlement choice must be recorded once.

## POL-MEM-v1#6 Ledger control

### POL-MEM-v1#6.1 Derived balance

The membership ledger is authoritative. A displayed balance may be rebuilt from the
ledger but cannot replace it.

### POL-MEM-v1#6.2 Corrections

A correction or reversal is appended with its source, reason, and approval. Existing
ledger entries are not edited or deleted.

## POL-MEM-v1#7 Roles and responsibilities

### POL-MEM-v1#7.1 Membership Operations

Membership Operations maintains plan entitlements and terms, reviews ledger and
allocation discrepancies, and submits supported correction requests.

### POL-MEM-v1#7.2 Customer Operations and Finance Operations

Customer Operations explains balances using the ledger and appointment history.
Finance Operations confirms renewal-payment status when entitlement depends on a
successful membership charge.

## POL-MEM-v1#8 Records and customer communication

### POL-MEM-v1#8.1 Required records

Luma retains the membership version, plan entitlement, grants, expirations,
consumptions, source appointments, allocations, reversals, corrections, approvals,
and relevant renewal-payment results.

### POL-MEM-v1#8.2 Plain-language explanation

Customer communications describe credits as added, used, expired, or restored and
identify the related membership period or appointment when known. Internal ledger
and approval terminology is used only when it helps resolve the inquiry.

## POL-MEM-v1#9 Related documents

### POL-MEM-v1#9.1 Supporting policies

Cancellation outcomes are governed by `POL-CAN`; payment and renewal reconciliation
is governed by `POL-PAY`; corrective authorization is governed by `POL-ADJ`.

## POL-MEM-v1#10 Document administration

### POL-MEM-v1#10.1 Revision history

| Version | Approved on | Effective from | Change summary |
|---|---|---|---|
| 1 | 2023-12-15 | 2024-01-01 | Initial controlled membership-credit policy. |
