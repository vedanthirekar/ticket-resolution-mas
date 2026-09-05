# Membership Credit Policy

| Metadata | Value |
|---|---|
| Policy ID | `POL-MEM` |
| Version | `1` |
| Effective from | 2024-01-01 00:00 UTC |
| Effective through | 2025-12-31 23:59:59 UTC |
| Scope | Essential, Plus, and Premier memberships |
| Superseded by | `POL-MEM` version 2 |

## POL-MEM-v1#1 Purpose

This policy defines monthly membership grants, consumption, expiration, and
correction before January 1, 2026.

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

