# Luma Wellness Operational Data Contract

Status: Gate A approved September 3, 2026

Contract candidate: `luma_business_v1`

This document states which operational facts Luma's existing systems retain and
what those facts mean. It is intentionally independent of a physical database
schema and any case-resolution implementation.

## 1. Contract principles

1. Public references such as `APPT-000882` are stable and safe for operational use.
2. History is append-only. Current state is a projection, not a replacement for
   evidence.
3. Financial truth is expressed in integer cents and provider lifecycle events.
4. Policy applicability is temporal and scoped.
5. Unknown, missing, contradictory, and unavailable are distinct data conditions.
6. Complaint text never becomes an operational fact merely because it names an
   appointment, amount, or alleged cause.

## 2. Stable fact domains

### Organization and catalog

- Location identity, named timezone, business hours, closures, and capacity
- Employee identity, active interval, role, location assignments, qualifications,
  and working schedules
- Service identity, active interval, duration, price, credit cost, qualifications,
  compatible add-ons, location offering, and online-booking configuration

### Customer

- Customer public reference and active status
- Verified contact channels used for identity matching
- Membership association
- Creation and deactivation times

Contact values are sensitive. Operational consumers receive masked contact data
unless exact values are required for an authorized workflow.

### Appointment evidence

- Stable appointment reference
- Customer, location, service, assigned provider, quoted interval, price, currency,
  booking channel, and current state
- Ordered immutable appointment events with actor, initiator, reason, event time,
  recorded time, channel, and correlation/causation references
- Reschedule predecessor/successor references
- Provider reassignment/transfer history
- Fee obligations and associated payment references

### Payment evidence

- Stable payment and obligation references
- Customer, tender category, currency, intended/authorized/captured/refunded amounts,
  current state, and provider reference
- Ordered provider/internal lifecycle events
- Refund requests and successful/failed refund transactions
- Invoice item or appointment/fee association establishing what was paid

Matching amount, customer, and time alone does not establish a duplicate; the
shared obligation and absence of a distinct fulfilled item do.

### Membership evidence

- Stable membership and plan references, state, effective interval, billing cycle,
  and applicable terms version
- Immutable credit ledger entries and explicit grant-to-consumption allocations
- Derived available balance at an as-of instant
- Appointment association for consumption and fee forfeiture
- Correction/reversal source references and structured reasons

### Booking evidence

- Location-service configuration and effective interval
- Provider qualification, location assignment, schedule, and busy intervals
- Resource capacity and blocks
- Lead-time, horizon, customer eligibility, and temporary availability rules
- Booking-search or submission attempt, requested parameters, result, reason codes,
  correlation reference, and committed appointment if any

The contract does not promise that every casual availability search is retained.
It does retain submitted booking attempts and their definitive result.

### Policy evidence

- Stable policy ID, version, title, effective interval, scope, and supersession link
- Stable section ID, heading, ordered body text, and parent section
- Location/service/plan applicability metadata

## 3. Supported case families and evidence contract

`Required` means a definitive outcome cannot be established without the fact.
`Conditional` facts are required when an applicable policy exception introduces
the condition.

| Case family | Required evidence | Conditional evidence | Supported business outcomes |
|---|---|---|---|
| `duplicate_payment` | customer identity; payment attempts; captured amounts; obligation/item associations; payment/refund policy | appointment fulfillment; membership tender; prior refund status | explain distinct charges; refund later duplicate capture; report authorization hold; investigate |
| `cancellation_fee_dispute` | customer identity; appointment; cancellation/no-show events; fee obligation/payment; policy effective at event time | reschedule link; accepted provider transfer and fulfillment; corrected events | retain fee; waive uncaptured fee; refund captured fee; investigate |
| `missing_appointment` | customer identity; appointment search; event/reschedule history; submitted booking attempts | duplicate customer profile; notification correlation; payment obligation | identify active/replacement/cancelled appointment; explain rejected/failed attempt; propose booking recovery; investigate |
| `membership_credit_discrepancy` | customer identity; membership terms/state; complete relevant ledger slice; allocations; related appointment attendance | cancellation events; correction/reversal chain; payment state | explain balance; restore/correct credits; retain consumption/expiry; investigate |
| `online_booking_unavailable` | requested location/service/time; effective location-service config; hours; providers; qualifications; schedule/busy intervals; booking rules | room/equipment capacity; customer eligibility; temporary blocks; recorded booking attempt | explain legitimate unavailability; identify configuration/technical issue; propose operational correction; investigate |

An unrecognized case may be classified as out of scope, but it may not be forced
into the closest supported family.

## 4. Evidence condition vocabulary

Every expected fact can be represented as one of:

| Condition | Meaning | Decision implication |
|---|---|---|
| `present` | Authoritative record was retrieved and has a usable value | May support a decision |
| `known_absent` | Authoritative search succeeded and proves no matching record exists | May itself support an explanation |
| `missing` | A record expected from the business process is absent | Human investigation for definitive action |
| `unknown` | Record exists but the relevant field is explicitly unknown | Human investigation when material |
| `contradictory` | Two authoritative records cannot both be true under the contract | Human investigation |
| `unavailable` | Source could not be queried or repeatedly failed | Retry, then human investigation |
| `not_applicable` | Fact is not required under the applicable rule | Does not count as missing |

## 5. Disposition and outcome vocabulary

Business outcome describes what should happen. Disposition describes the path by
which the case proceeds.

### Outcomes

- `explain_no_error`
- `explain_authorization_hold`
- `refund_payment`
- `waive_uncaptured_fee`
- `restore_membership_credits`
- `correct_membership_ledger`
- `propose_booking_recovery`
- `propose_configuration_correction`
- `out_of_scope`
- `no_determination`

Corrective outcomes include target public reference, quantity or amount when
applicable, currency, reason code, evidence references, and policy citations.

### Dispositions

- `AUTO_RESOLVE`: verified explanation requiring no state mutation.
- `HUMAN_APPROVAL`: evidence supports a specific mutation, which remains pending
  until an authorized employee approves it.
- `HUMAN_INVESTIGATION`: facts conflict, required facts or policy are missing,
  identity is unresolved, the case is out of scope, or the supported correction is
  not safely expressible.

There is no `WAITING_FOR_CUSTOMER` disposition in this contract. If existing data
cannot establish identity or required facts, the case requires human investigation.

## 6. Temporal interpretation

- Appointment notice windows use the appointment location's local timezone.
- Duration calculations use timezone-aware instants so daylight-saving transitions
  are not treated as ordinary equal-length wall-clock intervals.
- Appointment rules use the policy effective at the triggering event time.
- Membership grant expiry uses the membership terms effective at grant time.
- Payment/refund rules use the obligation and transaction times, not support-case
  receipt time.
- Catalog changes do not change historical appointment quotes.

## 7. Data quality and freeze requirements

Before a generated dataset receives this contract label:

- All database and service-layer invariants that can be tested offline pass.
- Counts and distributions fall inside the reviewed generation manifest.
- Every intended resolvable case has its required authoritative evidence.
- Every intended escalation case has a declared reason in a hidden anomaly manifest.
- Policy effective intervals have no unexplained overlap or gap.
- All public references are unique and all event sequences are reproducible from a
  fixed seed.
- A data fingerprint and generation manifest are recorded with the contract label.
