# Membership Credit Policy

| Metadata | Value |
|---|---|
| Policy ID | `POL-MEM` |
| Version | `2` |
| Effective from | 2026-01-01 00:00 UTC |
| Effective through | Open-ended |
| Scope | Essential, Plus, and Premier memberships |
| Supersedes | `POL-MEM` version 1 |

## POL-MEM-v2#1 Purpose

This policy defines monthly membership grants, consumption, expiration, and
correction from January 1, 2026.

## POL-MEM-v2#2 Plan grants

### POL-MEM-v2#2.1 Monthly entitlement

An active membership receives its plan's integer credit grant after successful
monthly renewal: Essential 1, Plus 2, and Premier 4.

### POL-MEM-v2#2.2 Rollover ceiling

Before a new grant, unused credits are capped at 3 for Essential, 6 for Plus, and 12
for Premier. Credits above the ceiling expire through ledger entries before the new
grant is applied.

### POL-MEM-v2#2.3 Pause and cancellation

Paused, cancelled, and expired memberships receive no future grant. Existing grants
retain their original expiration.

## POL-MEM-v2#3 Credit validity

### POL-MEM-v2#3.1 Consumption order

Eligible services consume earliest-expiring available credits first. Allocations to
source grants must be retained.

### POL-MEM-v2#3.2 Expiration

Each grant made on or after January 1, 2026 expires 90 days after its grant
timestamp. Earlier grants retain the 60-day expiry assigned under version 1.

## POL-MEM-v2#4 Appointment settlement

### POL-MEM-v2#4.1 Fulfilled service

A completed eligible service consumes the catalog credit cost quoted on its
appointment. Cash-only services and add-ons do not consume membership credits.

## POL-MEM-v2#5 Cancellation effects

### POL-MEM-v2#5.1 Provider or business cancellation

Credits consumed for an appointment not fulfilled because the provider or business
cancelled must be restored through a reversal or correction linked to the original
consumption.

### POL-MEM-v2#5.2 Customer late cancellation or no-show

When the effective cancellation policy allows a charge, Luma may retain credits
allocated to the appointment instead of collecting the cash fee, up to the booked
service's credit cost. Luma must not both retain full credits and collect the full
cash fee for the same cancellation obligation.

## POL-MEM-v2#6 Ledger control

### POL-MEM-v2#6.1 Derived balance

The immutable ledger and allocation records are authoritative. A stale or incorrect
displayed balance is rebuilt from the ledger without changing valid entries.

### POL-MEM-v2#6.2 Corrections and broken chains

A correction or reversal is appended with the exact source where available, a
structured reason, and approval. Missing, duplicated, or contradictory ledger
entries require investigation before a correction quantity is chosen.

