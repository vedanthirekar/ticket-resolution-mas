# Payments and Refunds Policy

| Metadata | Value |
|---|---|
| Policy ID | `POL-PAY` |
| Version | `1` |
| Effective from | 2024-01-01 00:00 UTC |
| Effective through | Open-ended |
| Scope | All Luma-collected payments in USD |
| Supersedes | None |

## POL-PAY-v1#1 Purpose

This policy defines payment lifecycle interpretation, duplicate capture review, and
refund limits.

## POL-PAY-v1#2 Definitions

### POL-PAY-v1#2.1 Obligation

An obligation is the item Luma is entitled to collect: a fulfilled service, add-on,
approved fee, gratuity, tax item, or other itemized amount.

### POL-PAY-v1#2.2 Capture and authorization

An authorization reserves funds. A capture collects funds. Only a successful
capture can be refunded.

## POL-PAY-v1#3 Duplicate review

### POL-PAY-v1#3.1 Duplicate capture

Two successful captures are duplicates when they settle the same obligation and
the later capture has no distinct fulfilled or itemized consideration. Similar
amount, payment method, or timing helps locate candidates but does not prove a
duplicate. The later duplicate capture is refundable.

### POL-PAY-v1#3.2 Distinct charges

Charges for separate appointments, add-ons, gratuities, taxes, or valid fees are
distinct even if their amounts and timestamps are similar. Each must retain its
item association.

## POL-PAY-v1#4 Authorization handling

### POL-PAY-v1#4.1 Uncaptured authorization

An authorization that has not been captured is not a completed charge. If still
open, it may be voided through the payment provider; otherwise it is allowed to
expire. It must never be submitted as a refund.

## POL-PAY-v1#5 Refunds

### POL-PAY-v1#5.1 Refundable amount

A successful refund must be positive and cannot exceed captured amount minus prior
successful refunds. Pending or failed refunds do not reduce refundable amount.

### POL-PAY-v1#5.2 Previously refunded charge

A fully refunded payment cannot be refunded again. Staff may explain the successful
refund using its provider reference and completion time.

### POL-PAY-v1#5.3 Original tender

Refunds return to the original captured tender unless a separately documented legal
or provider constraint requires staff handling.

## POL-PAY-v1#6 Reconciliation

### POL-PAY-v1#6.1 Missing or unavailable provider truth

Provider lifecycle events are authoritative for capture, void, and refund success.
If provider truth remains unavailable or conflicts with internal records, staff must
reconcile the payment before another financial action.

