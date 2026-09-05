# Actor and Event Semantics

Status: Gate A approved September 3, 2026

## 1. Why actor and initiator are separate

The event author is who wrote or transmitted the record. The initiating party is
who caused the underlying business event. They are not interchangeable.

Example: a customer telephones the studio and Maya records the cancellation.
`actor_type=employee`, while `initiating_party=customer`. Treating Maya as the
initiator would produce the wrong cancellation-fee decision.

## 2. Actor types

| Actor type | Meaning | Example identifier |
|---|---|---|
| `customer` | Authenticated customer action | customer public reference |
| `employee` | Authenticated Luma employee action | employee public reference |
| `system` | Luma-owned automated process | stable component name |
| `external_provider` | Third party supplying an event | payment provider or messaging provider |

Actor type and actor reference describe authorship only. An external provider event
also carries its provider event reference to support idempotency and reconciliation.

## 3. Initiating parties

When causation matters, `initiating_party` is one of:

- `customer`
- `provider`
- `business`
- `system`
- `unknown`
- `not_applicable`

`provider` means the assigned practitioner; `business` means Luma for operational
reasons not attributable to that practitioner, such as a building closure. `system`
is used only when an automated rule initiated the business change, not merely when
software recorded a human action. `unknown` is a real evidence gap and cannot be
inferred from the author.

## 4. Canonical event envelope

Every material event promises the following semantic fields, regardless of its
future physical table representation:

| Field | Meaning |
|---|---|
| Event reference | Stable, unique business reference |
| Aggregate reference | Appointment, payment, membership, or booking-attempt reference |
| Event type | Stable machine-readable meaning |
| Event time | When the business event occurred |
| Recorded time | When Luma persisted the event |
| Actor type/reference | Who authored or transmitted the event |
| Initiating party | Who caused it when relevant |
| Reason code | Structured explanation from the controlled vocabulary |
| Channel | `web`, `mobile`, `phone`, `front_desk`, `batch`, `provider_webhook`, or `internal` |
| Correlation reference | Joins actions belonging to one business operation |
| Causation reference | Event or command that directly caused this event, when known |
| Metadata | Event-specific structured details; never a substitute for core fields |

Event time and recorded time are timezone-aware instants. The location timezone is
used to evaluate local notice windows and display time. Backfilled events may have a
recorded time later than event time but must carry a backfill reason.

## 5. Appointment cancellation reasons

| Reason code | Normal initiating party | Meaning |
|---|---|---|
| `customer_request` | customer | Customer chose not to attend |
| `provider_unavailable` | provider or business | Assigned provider could not fulfill service |
| `location_closed` | business | Location could not operate |
| `service_unavailable` | business | Required service/resource unavailable |
| `rescheduled` | customer, provider, or business | Reservation replaced by a linked appointment |
| `eligibility_not_met` | business | Documented service eligibility rule failed |
| `duplicate_booking` | customer, employee, or system | Duplicate reservation removed |
| `other` | any except not_applicable | Structured details required |
| `unknown` | unknown | Source did not establish causation |

Reason alone does not override initiating party. A suspicious pairing is retained
but marked as a contradiction for investigation.

## 6. Corrections and contradictions

Events are append-only. A correction event identifies the incorrect source event,
the corrected structured values, the reason, and its approving employee. Consumers
retain both events and use the latest valid correction for the projected state.

The following are contradictions rather than facts to guess around:

- Two uncorrected cancellation events with different initiating parties.
- A completed appointment followed by an ordinary cancellation.
- A refund success whose amount exceeds remaining captured funds.
- A membership reversal that points to no ledger entry.
- A committed booking attempt referencing no appointment or multiple appointments.

Unknown values, absent events, contradictions, and technical read failures are four
different conditions and must remain distinguishable.

## 7. Evidence interpretation rules

- Customer complaint text is a claim, not an operational event.
- Current state alone does not prove who caused a transition; use events.
- Employee authorship alone does not prove employee or business initiation.
- Payment provider status is authoritative for authorization, capture, void, and
  refund success; internal requests alone are not proof of success.
- A derived membership balance is useful, but ledger entries prove its components.
- Policy applicability uses event time, location, and policy scope, not case receipt
  time.
