# Online Booking and Appointment Records Policy

| Metadata | Value |
|---|---|
| Policy ID | `POL-BOOK` |
| Version | `1` |
| Document type | Internal operating policy |
| Policy owner | Vice President, Service Operations |
| Approved by | Chief Operating Officer |
| Document classification | Internal |
| Intended audience | Digital Product, Customer Operations, Location Leadership |
| Approved on | 2023-12-15 |
| Review cycle | Annual and upon material booking-platform change |
| Effective from | 2024-01-01 00:00 UTC |
| Effective through | Open-ended |
| Scope | All Luma locations, services, and customer booking channels |
| Supersedes | None |

## POL-BOOK-v1#1 Purpose

This policy establishes the conditions under which services may be reserved through
Luma's customer booking channels and the records used to resolve unsuccessful,
rescheduled, or missing-appointment reports.

## POL-BOOK-v1#2 Reservation rule

### POL-BOOK-v1#2.1 Atomic commit

A search result is not a reservation. An appointment exists only after current
availability is revalidated and the submitted booking attempt commits. A committed
attempt references exactly one appointment.

### POL-BOOK-v1#2.2 Idempotent submission

Retries carrying the same customer submission key return the original outcome and
must not create a second appointment.

## POL-BOOK-v1#3 Availability requirements

### POL-BOOK-v1#3.1 Provider eligibility

At least one active provider must be assigned to the location, qualified for the
service, scheduled, and free for the complete interval.

### POL-BOOK-v1#3.2 Location hours

The complete service interval, including duration-changing add-ons, must lie inside
effective location hours and outside closure blocks.

### POL-BOOK-v1#3.3 Service configuration

The service must be active and explicitly enabled for online booking at the selected
location. A service may remain bookable by employees when online booking is off.

### POL-BOOK-v1#3.4 Lead time

Standard services require two hours' lead time. Advanced peels require 24 hours.
Location leads may create staff-assisted bookings inside the online lead time.

### POL-BOOK-v1#3.5 Booking horizon

Online appointments may begin no more than 60 calendar days from the location's
current local date.

### POL-BOOK-v1#3.6 Resource capacity

The required room, station, or equipment capacity must remain available for the
complete interval. Provider availability alone is insufficient.

### POL-BOOK-v1#3.7 Customer eligibility

Services with documented eligibility requirements are withheld when the customer's
record does not satisfy them. Lack of eligibility for one service does not block
unrelated services.

## POL-BOOK-v1#4 Result explanations

### POL-BOOK-v1#4.1 Minimum disclosure

Customer-facing explanations may name ordinary restrictions such as hours, lead
time, service offering, or lack of availability. They must not expose another
customer's booking or private provider details.

## POL-BOOK-v1#5 Booking attempts

### POL-BOOK-v1#5.1 Committed

A committed attempt returns its appointment reference even if notification delivery
later fails.

### POL-BOOK-v1#5.2 Rejected

A rejected submitted attempt records the business reason and creates no appointment.

### POL-BOOK-v1#5.3 Failed or unexplained

A technical failure creates no presumed reservation. If all known availability
requirements were satisfied but the service returned no slot or failed, operations
reviews configuration and may assist with a new booking.

## POL-BOOK-v1#6 Missing appointment review

### POL-BOOK-v1#6.1 Rescheduled appointment

Staff checks predecessor and replacement links before declaring an appointment
missing. An active replacement is reported with its own reference and schedule.

### POL-BOOK-v1#6.2 Payment is not booking proof

A payment without a clear appointment or obligation association does not prove that
an appointment committed. The payment discrepancy and booking history require
reconciliation.

### POL-BOOK-v1#6.3 Ambiguous customer identity

Staff must not silently select or merge multiple plausible customer profiles.
Identity ambiguity requires investigation.

## POL-BOOK-v1#7 Record quality

### POL-BOOK-v1#7.1 Missing availability inputs

Availability cannot be diagnosed definitively when required configuration,
schedule, qualification, capacity, or attempt records are missing or unavailable.

## POL-BOOK-v1#8 Roles and responsibilities

### POL-BOOK-v1#8.1 Digital Product

Digital Product maintains the booking workflow, customer-facing status messages,
submission controls, and monitoring needed to distinguish a rejected request from a
technical failure.

### POL-BOOK-v1#8.2 Location leadership

Location leadership maintains accurate hours, closures, service offerings,
provider assignments, qualifications, schedules, and resource capacity.

### POL-BOOK-v1#8.3 Customer Operations

Customer Operations explains recorded outcomes, protects other customers' and
employees' private information, and escalates incomplete or conflicting source
records. Staff must not promise a reservation until a committed appointment exists.

## POL-BOOK-v1#9 Records and privacy

### POL-BOOK-v1#9.1 Required booking records

Submitted attempts retain their customer, channel, requested service, location,
provider preference when supplied, requested time, result, reason code, correlation
reference, and committed appointment reference when successful.

### POL-BOOK-v1#9.2 Minimum necessary disclosure

Internal diagnostics may identify the rule or source record that prevented a
booking. Customer communications disclose only the minimum information needed to
explain the result and must not reveal another customer's appointment or sensitive
employee information.

## POL-BOOK-v1#10 Related documents

### POL-BOOK-v1#10.1 Supporting policies

Payment discrepancies are governed by `POL-PAY`; cancellation and provider
disruption are governed by `POL-CAN`; corrective actions and approvals are governed
by `POL-ADJ`.

## POL-BOOK-v1#11 Document administration

### POL-BOOK-v1#11.1 Revision history

| Version | Approved on | Effective from | Change summary |
|---|---|---|---|
| 1 | 2023-12-15 | 2024-01-01 | Initial controlled online-booking and appointment-record policy. |
