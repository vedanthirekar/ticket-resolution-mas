# Payments and Refunds Policy

| Metadata | Value |
|---|---|
| Policy ID | `POL-PAY` |
| Version | `1` |
| Document type | Internal financial operations policy |
| Policy owner | Controller |
| Approved by | Chief Financial Officer |
| Document classification | Internal |
| Intended audience | Finance Operations, Customer Operations, Location Leadership |
| Approved on | 2023-12-15 |
| Review cycle | Annual and upon material payment-provider change |
| Effective from | 2024-01-01 00:00 UTC |
| Effective through | Open-ended |
| Scope | All Luma-collected payments in USD |
| Supersedes | None |

## POL-PAY-v1#1 Purpose

This policy establishes how Luma interprets payment lifecycle records, determines
whether charges represent the same obligation, and controls refunds of
Luma-collected payments.

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

## POL-PAY-v1#7 Roles and responsibilities

### POL-PAY-v1#7.1 Customer Operations

Customer Operations identifies the disputed transaction, gathers appointment and
itemized obligation evidence, explains supported results, and submits any proposed
refund through the approved adjustment process.

### POL-PAY-v1#7.2 Finance Operations

Finance Operations owns payment reconciliation, monitors processor exceptions, and
investigates conflicting settlement, refund, or tender records.

### POL-PAY-v1#7.3 Approver

An authorized approver confirms the payment, refundable balance, reason, and
supporting policy before a refund is executed. A reviewer must not represent a
pending provider request as completed.

## POL-PAY-v1#8 Customer communication and records

### POL-PAY-v1#8.1 Plain-language explanation

Customer-facing explanations distinguish a pending authorization from a posted
charge and identify the related service or fee when known. Internal processor,
risk, and fraud-control details are disclosed only when authorized.

### POL-PAY-v1#8.2 Required records

Luma retains the invoice and item association, payment lifecycle events, processor
references, refund requests and results, approval evidence, and customer
communication under the corporate financial-records schedule.

## POL-PAY-v1#9 Related documents

### POL-PAY-v1#9.1 Supporting policies

`POL-CAN` determines whether a cancellation or no-show fee is owed; `POL-MEM`
governs credit settlement; `POL-ADJ` governs refund authorization and execution.

## POL-PAY-v1#10 Document administration

### POL-PAY-v1#10.1 Revision history

| Version | Approved on | Effective from | Change summary |
|---|---|---|---|
| 1 | 2023-12-15 | 2024-01-01 | Initial controlled payments and refunds policy. |
