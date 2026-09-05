# Luma Wellness Operational State Machines

Status: Gate A approved September 3, 2026

These state machines define business meaning. An event is the immutable record of a
transition; the current state is a convenient projection of the accepted events.

## 1. Appointment

### States

| State | Meaning | Terminal |
|---|---|---|
| `scheduled` | Reservation committed and awaiting confirmation or service | No |
| `confirmed` | Customer or employee confirmed attendance intent | No |
| `checked_in` | Customer arrived and service fulfillment may begin | No |
| `completed` | Booked service was fulfilled | Yes |
| `cancelled` | Reservation ended before fulfillment | Yes |
| `no_show` | Customer did not arrive within the attendance grace period | Yes |

### Valid transitions

| From | To | Establishing event | Required transition facts |
|---|---|---|---|
| none | `scheduled` | `appointment_created` | customer, service, location, provider, quoted interval |
| `scheduled` | `confirmed` | `appointment_confirmed` | confirmation channel and event time |
| `scheduled` | `checked_in` | `customer_checked_in` | arrival time; confirmation is not mandatory |
| `confirmed` | `checked_in` | `customer_checked_in` | arrival time |
| `checked_in` | `completed` | `service_completed` | completion time and fulfilling provider |
| `scheduled` | `cancelled` | `appointment_cancelled` | initiating party, reason, event time |
| `confirmed` | `cancelled` | `appointment_cancelled` | initiating party, reason, event time |
| `scheduled` | `no_show` | `appointment_marked_no_show` | grace period elapsed, author, event time |
| `confirmed` | `no_show` | `appointment_marked_no_show` | grace period elapsed, author, event time |

`checked_in` cannot normally become `cancelled` or `no_show`. If service cannot be
delivered after check-in, staff records `service_not_fulfilled` and routes the record
for an operational correction; the historical check-in remains visible.

### Non-state-changing events

- `appointment_confirmation_sent`
- `appointment_reminder_sent`
- `provider_reassigned`
- `appointment_note_added`
- `appointment_reschedule_linked`
- `appointment_event_corrected`

A reschedule is not a state transition on a single mutable reservation. It is a
cancelled prior appointment plus a newly scheduled appointment joined by reciprocal
reschedule references.

### Invalid transition treatment

Invalid transitions are rejected during normal processing. If an external or legacy
record produces an impossible sequence, the raw event is retained as a quarantined
data-quality anomaly and does not update the projected current state.

## 2. Payment

### States and amounts

| State | Meaning |
|---|---|
| `created` | Internal payment intent exists; no provider authorization is known |
| `authorized` | Provider reserved funds but Luma has not captured them |
| `captured` | Positive funds were captured and no successful refund exists |
| `partially_refunded` | Successful refunds total more than zero and less than captured amount |
| `refunded` | Successful refunds equal captured amount |
| `voided` | Uncaptured authorization was released or the created intent was cancelled |
| `failed` | Authorization or capture definitively failed |

- `amount`: amount Luma intended to collect for the obligation.
- `authorized_amount`: amount the provider approved for later capture.
- `captured_amount`: settled amount successfully collected.
- `refunded_amount`: sum of successful refund transactions against the capture.
- `refundable_amount`: `captured_amount - refunded_amount`.

All amounts are non-negative integer cents in the same currency. A refund request
does not affect `refunded_amount` until it succeeds.

### Valid transitions

| From | To | Establishing event | Important constraint |
|---|---|---|---|
| none | `created` | `payment_created` | unique payment reference and obligation |
| `created` | `authorized` | `payment_authorized` | authorization reference and positive amount |
| `created` | `captured` | `payment_captured` | immediate-capture flows may skip stored authorized state |
| `authorized` | `captured` | `payment_captured` | capture does not exceed authorization unless provider permits it |
| `created` | `failed` | `payment_failed` | failure stage and provider code |
| `authorized` | `failed` | `payment_failed` | capture failure; authorization disposition recorded |
| `created` | `voided` | `payment_voided` | no capture exists |
| `authorized` | `voided` | `payment_voided` | provider release accepted |
| `captured` | `partially_refunded` | `refund_succeeded` | cumulative refunds below capture |
| `captured` | `refunded` | `refund_succeeded` | cumulative refunds equal capture |
| `partially_refunded` | `partially_refunded` | `refund_succeeded` | cumulative refunds remain below capture |
| `partially_refunded` | `refunded` | `refund_succeeded` | cumulative refunds equal capture |

`failed`, `voided`, and `refunded` are terminal. A later retry creates a new payment
record linked to the same obligation rather than reviving the terminal record.

## 3. Membership

### States

| State | Meaning | Monthly billing/grants |
|---|---|---|
| `active` | Enrolled and eligible to renew | Continue |
| `paused` | Temporarily suspended | Stop until resumed |
| `cancelled` | Customer ended future renewal | Stop |
| `expired` | Membership ended because its paid term elapsed or renewal failed past grace | Stop |

### Valid transitions

| From | To | Establishing event |
|---|---|---|
| none | `active` | `membership_activated` |
| `active` | `paused` | `membership_paused` |
| `paused` | `active` | `membership_resumed` |
| `active` | `cancelled` | `membership_cancelled` |
| `paused` | `cancelled` | `membership_cancelled` |
| `active` | `expired` | `membership_expired` |
| `paused` | `expired` | `membership_expired` |

Cancelled or expired memberships are not reactivated. A returning customer receives
a new membership linked to the same customer.

### Credit ledger

Credit balance is derived from immutable entries:

| Entry type | Sign | Meaning | Must reference |
|---|---:|---|---|
| `grant` | positive | Scheduled plan entitlement | membership, plan cycle, expiry |
| `consume` | negative | Eligible service used credits | appointment and source grant allocation |
| `expire` | negative | Unused grant reached expiry | source grant |
| `correction` | positive or negative | Staff-approved accounting correction | reason and evidence reference |
| `reversal` | opposite of source | Reverses an erroneous prior entry | exact source ledger entry |

The derived balance may never be made negative by a normal consumption or
expiration entry. Corrections that would produce a negative balance are rejected.
Consumption allocations use earliest expiry first and remain explicit even when one
service consumes credits from multiple grants.

## 4. Online booking attempt

A booking search does not reserve capacity. A submitted booking attempt has its own
short state progression so failures can be distinguished from missing records.

| State | Meaning |
|---|---|
| `received` | Submission received with a correlation reference |
| `validating` | Eligibility and current availability are being checked |
| `committed` | Appointment was created atomically |
| `rejected` | A business rule made the requested slot unavailable |
| `failed` | A technical failure prevented a definitive result |

`received -> validating -> committed|rejected|failed` is the only valid progression.
A committed attempt must reference exactly one appointment. A retry uses a stable
idempotency key: it returns the original result rather than creating a second
appointment.
