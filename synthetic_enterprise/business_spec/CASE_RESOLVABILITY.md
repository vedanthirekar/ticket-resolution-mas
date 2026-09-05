# Case Resolvability Against `luma_business_v1`

Status: Gate C approved September 3, 2026

This document was written after freezing the operational system. It describes what
future case-resolution software may determine from existing records; it does not
prescribe agent prompts or provide a runtime answer table.

## 1. Shared interpretation

Every investigation starts by establishing customer identity and relevant public
references. Complaint text is an allegation. Operational event streams establish
what occurred, payment-provider events establish financial lifecycle, membership
ledger/allocation rows establish credit accounting, and the policy version effective
on the material event date establishes the governing rule.

Evidence conditions remain distinct: present, known absent, missing, unknown,
contradictory, unavailable, and not applicable. Missing or contradictory required
evidence leads to human investigation, not a guessed outcome.

## 2. Resolvability summary

| Case family | Current data support | Definitive when | Must investigate when |
|---|---|---|---|
| Duplicate payment | Resolvable | Captures, obligation identity, itemization, fulfillment, and refund state agree | Obligation association, processor state, or item fulfillment is missing/conflicting |
| Cancellation-fee dispute | Resolvable, including temporal rules | Appointment events prove initiator/time and fee/payment plus effective policy are present | Initiator/event history, fee link, processor state, or applicable policy is missing/conflicting |
| Missing appointment | Partially resolvable by design | Appointment/reschedule or submitted booking-attempt history explains the absence | Identity is ambiguous or neither appointment nor retained submitted attempt establishes what happened |
| Membership-credit discrepancy | Resolvable | Complete ledger, allocations, attendance/cancellation facts, and effective terms reconcile | Ledger chain, source appointment, allocation, or policy terms are missing/conflicting |
| Online booking unavailable | Resolvable for retained attempts | Configuration, hours, provider qualification/schedule, resource capacity, blocks, and attempt result are available | No submitted attempt was retained or a required effective input is missing/unavailable |

## 3. Duplicate payment

Typical allegation: “I was charged twice for the same appointment.”

| Required fact | Authoritative source | Available in v1 |
|---|---|---|
| Customer/payment identity | `customers`, `payments` public references | Yes |
| Successful capture state | `payment_events`; payment projection | Yes |
| Obligation settled | `payments.obligation_reference`, `invoices`, `invoice_items` | Yes |
| Distinct fulfilled consideration | invoice items and appointment completion events | Yes |
| Prior refund amount/status | `refunds`, payment events/projection | Yes |
| Effective refund policy | `POL-PAY` version/sections | Yes |

Canonical contrast:

- `APPT-DUP-PAY` has two captured payments sharing one obligation and only one
  fulfilled service.
- `APPT-DISTINCT-A` and `APPT-DISTINCT-B` have equal-looking $120 captures but
  distinct invoices, appointments, and fulfilled obligations.
- `APPT-AUTH-HOLD` has a $60 authorization and zero captured amount, so it cannot be
  treated as a refundable charge.

Supported outcomes are explanation of distinct charges or authorization hold,
refund of the later duplicate capture subject to approval, explanation of an
existing refund, or human investigation.

The system cannot determine an external bank's display/settlement timing beyond the
processor events retained by Luma.

## 4. Cancellation-fee dispute

Typical allegation: “I was charged even though the provider cancelled.”

| Required fact | Authoritative source | Available in v1 |
|---|---|---|
| Appointment and quoted service | `appointments` | Yes |
| Cancellation/no-show transition | `appointment_events` | Usually; one declared missing-evidence incident |
| Event author vs initiating party | separate event columns | Yes when recorded |
| Notice interval and location timezone | event/start timestamps plus `locations.timezone` | Yes |
| Fee obligation and captured state | `invoice_items`, `invoices`, `payments`, `payment_events` | Yes |
| Effective cancellation/refund rules | `POL-CAN` and `POL-PAY` versions/sections | Yes |
| Accepted transfer fulfillment | provider-reassignment metadata plus completion event | Conditional and present for canonical transfer |

Canonical coverage includes provider cancellation with an incorrect captured $80
fee, customer cancellation on both sides of the v2 notice window, valid no-show,
v1/v2 boundary events, missing cancellation evidence, conflicting initiators, and
an accepted/fulfilled provider transfer.

The transfer case is the justified supplemental-evidence path: initial cancellation
facts may suggest business disruption, while `POL-CAN-v2#4.2` requires checking
customer acceptance and actual fulfillment before deciding whether the service
obligation remained valid.

Supported outcomes are retain fee, waive an uncaptured fee, refund a captured fee
subject to approval, explain a completed accepted transfer, or investigate.

## 5. Missing appointment

Typical allegation: “My appointment disappeared.”

| Required fact | Authoritative source | Available in v1 |
|---|---|---|
| Customer identity | customer profile and verified contacts | Yes; ambiguous matches can still occur |
| Current/historical appointment | appointment plus ordered events | Yes when a reservation committed |
| Reschedule replacement | predecessor relationship and reschedule events | Supported by schema |
| Submitted booking result | `booking_attempts` status/reason/appointment FK | Yes for retained submissions |
| Related payment obligation | invoices/payments and item association | Yes where one exists |

A committed attempt proves that an appointment existed even if notification failed.
A rejected or failed attempt proves no reservation committed. Payment without a
clear obligation/appointment association is not booking proof.

Supported outcomes are identify the active/replacement/cancelled appointment,
explain a rejected attempt, propose staff-assisted recovery after a technical
failure, or investigate.

The business does not retain every casual availability search. If there is no
appointment and no submitted attempt, the exact reason for an alleged historical
screen state is impossible to establish from v1.

## 6. Membership-credit discrepancy

Typical allegation: “Two credits were removed for one visit.”

| Required fact | Authoritative source | Available in v1 |
|---|---|---|
| Membership and applicable terms | `memberships`, `membership_plans`, `POL-MEM` | Yes |
| Grants/expiry/corrections | `membership_ledger` | Yes |
| Grant-to-consumption provenance | `membership_credit_allocations` | Yes |
| Service credit cost and fulfillment | appointment quote and completion events | Yes |
| Cancellation effects | appointment events plus effective cancellation policy | Yes |

`APPT-MEM-DUP` has two consumption entries for one one-credit service, each visible
through its source allocation. `APPT-MEM-CORRECT` has one correctly allocated
consumption for a completed eligible service. Historical expired grants are
represented by linked grant and expiration entries.

Supported outcomes are explain correct consumption/expiry, restore or correct
credits through an approved appended ledger entry, or investigate. A displayed
balance never overrides the ledger.

## 7. Online booking unavailable

Typical allegation: “The website will not let me book this provider and service.”

| Required fact | Authoritative source | Available in v1 |
|---|---|---|
| Requested customer/location/service/time/provider | submitted `booking_attempts` | Yes for retained submissions |
| Location offering and online flag | location service and effective booking settings | Yes |
| Hours and closures | business hours and blocks | Yes |
| Qualification/location assignment | employee-service and employee-location records | Yes |
| Provider schedule and busy intervals | schedules, appointments, blocks | Yes |
| Resource capacity | location resources and service setting | Yes |
| Lead time/horizon/eligibility | layered booking settings | Yes |

Canonical rejected attempts isolate employee override, missing qualification,
provider schedule, and location closure reasons. A separate technical-failure
attempt occurs while ordinary inputs are valid, supporting operational review
instead of a fabricated business restriction.

Supported outcomes are explain legitimate unavailability, identify a likely
configuration/technical issue, propose an approved operational correction, or
investigate. The system cannot reconstruct an unretained casual search.

## 8. Cross-family escalation facts

Every family requires human investigation when:

- customer/target identity cannot be established;
- an authoritative source remains unavailable after bounded retries;
- required records are missing or authoritative records conflict;
- no policy version applies exactly at the material event date;
- the issue is outside the five supported families;
- a correction target, amount, quantity, or safe idempotent action cannot be stated.

These conditions are explicit and do not depend on model self-confidence.
