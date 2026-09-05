# Luma Wellness Company Handbook

Document owner: Operations

Status: Draft operating specification

## 1. Company and service model

Luma Wellness is a fictional appointment-based wellness company. It provides
massage, skincare, assisted recovery, and wellness consultation services at three
company-operated studios. Customers may book online or through a studio employee,
pay per visit, or use eligible monthly membership credits.

Each appointment reserves one location, one service, one qualified provider, and
one customer for a defined local start and end time. Luma does not operate an open
marketplace: providers are employees or contracted practitioners administered by
Luma, prices are set by Luma, and payments are collected by Luma.

All monetary amounts are denominated in USD. Displayed service prices exclude any
late-cancellation or no-show charge and exclude location-specific sales tax where
applicable.

## 2. Locations

Hours below are local wall-clock hours. A location may close a bookable service
earlier than the building close when the service duration would extend past close.
Holiday closures and temporary blocks override normal hours.

| Reference | Studio | Timezone | Normal hours | Operational differences |
|---|---|---|---|---|
| LOC-IND | Indianapolis, Indiana | `America/Indiana/Indianapolis` | Mon-Thu 08:00-20:00; Fri 08:00-18:00; Sat 09:00-16:00; Sun closed | Full service catalog; recovery room has two concurrent stations |
| LOC-CHI | Chicago, Illinois | `America/Chicago` | Mon-Fri 07:00-20:00; Sat-Sun 09:00-17:00 | Full service catalog; earliest weekday appointments; facial room has one station |
| LOC-DEN | Denver, Colorado | `America/Denver` | Tue-Fri 09:00-19:00; Sat-Sun 09:00-16:00; Mon closed | No advanced peel services; altitude-recovery specialty; recovery room has three concurrent stations |

Location hours are not provider schedules. Both must permit the complete service
interval. Times are stored as instants but interpreted and displayed in the
appointment location's named timezone.

## 3. Workforce

Luma has fifteen active employees in the initial business snapshot. Location leads
can perform administrative work; only employees with an active qualification may
be assigned to the corresponding service.

| Reference | Name | Home location | Role | Qualification groups |
|---|---|---|---|---|
| EMP-001 | Maya Chen | Indianapolis | Location lead | operations |
| EMP-002 | Elena Ruiz | Indianapolis | Massage therapist | massage-core, massage-advanced |
| EMP-003 | Jordan Brooks | Indianapolis | Esthetician | facial-core, facial-advanced |
| EMP-004 | Priya Shah | Indianapolis | Recovery specialist | recovery, consultation |
| EMP-005 | Noah Williams | Indianapolis | Massage therapist | massage-core, prenatal |
| EMP-006 | Olivia Martin | Chicago | Location lead | operations, consultation |
| EMP-007 | Marcus Lee | Chicago | Massage therapist | massage-core, massage-advanced, sports |
| EMP-008 | Sofia Patel | Chicago | Esthetician | facial-core, facial-advanced |
| EMP-009 | Grace Kim | Chicago | Recovery specialist | recovery, consultation |
| EMP-010 | Daniel Ortiz | Chicago | Massage therapist | massage-core, prenatal |
| EMP-011 | Avery Johnson | Denver | Location lead | operations, consultation |
| EMP-012 | Riley Morgan | Denver | Massage therapist | massage-core, sports |
| EMP-013 | Layla Hassan | Denver | Esthetician | facial-core |
| EMP-014 | Ethan Nguyen | Denver | Recovery specialist | recovery, consultation, altitude-recovery |
| EMP-015 | Chloe Davis | Denver | Massage therapist | massage-core, massage-advanced, prenatal |

An employee may work at a non-home location only when an explicit location
assignment and schedule exist. Deactivation prevents future assignment but does not
alter historical appointments or events.

## 4. Service catalog

`Credit cost` is the number of membership credits consumed when the service is paid
with credits. A dash means the service is cash-only. Add-ons can only be attached to
a compatible primary appointment and do not create a standalone provider booking.

| Reference | Service | Minutes | Base price | Credit cost | Qualification | Location restriction |
|---|---|---:|---:|---:|---|---|
| SVC-001 | Swedish Massage 50 | 50 | $120 | 1 | massage-core | none |
| SVC-002 | Swedish Massage 80 | 80 | $175 | 2 | massage-core | none |
| SVC-003 | Deep Tissue 50 | 50 | $145 | 1 | massage-advanced | none |
| SVC-004 | Deep Tissue 80 | 80 | $205 | 2 | massage-advanced | none |
| SVC-005 | Sports Recovery Massage | 60 | $160 | 1 | sports | none |
| SVC-006 | Prenatal Massage | 60 | $150 | 1 | prenatal | none |
| SVC-007 | Hot Stone Massage | 80 | $215 | 2 | massage-advanced | none |
| SVC-008 | Essential Facial | 50 | $125 | 1 | facial-core | none |
| SVC-009 | Hydration Facial | 60 | $155 | 1 | facial-core | none |
| SVC-010 | Brightening Facial | 60 | $165 | 1 | facial-core | none |
| SVC-011 | Advanced Renewal Facial | 75 | $210 | 2 | facial-advanced | Indianapolis, Chicago |
| SVC-012 | Clarifying Facial | 50 | $140 | 1 | facial-core | none |
| SVC-013 | Advanced Peel | 45 | $190 | 2 | facial-advanced | Indianapolis, Chicago |
| SVC-014 | Compression Recovery | 30 | $55 | - | recovery | none |
| SVC-015 | Assisted Stretch | 30 | $70 | - | recovery | none |
| SVC-016 | Assisted Stretch Extended | 50 | $105 | 1 | recovery | none |
| SVC-017 | Recovery Circuit | 45 | $95 | 1 | recovery | none |
| SVC-018 | Altitude Recovery Session | 45 | $110 | 1 | altitude-recovery | Denver only |
| SVC-019 | Wellness Consultation | 30 | $50 | - | consultation | none |
| SVC-020 | Recovery Plan Consultation | 45 | $75 | - | consultation | none |
| SVC-021 | Aromatherapy Add-on | 0 | $20 | - | massage-core | compatible massage only |
| SVC-022 | Scalp Treatment Add-on | 15 | $30 | - | massage-core | compatible massage only |
| SVC-023 | Eye Treatment Add-on | 15 | $35 | - | facial-core | compatible facial only |
| SVC-024 | LED Treatment Add-on | 20 | $45 | - | facial-core | compatible facial only |
| SVC-025 | Percussion Therapy Add-on | 15 | $30 | - | recovery | compatible massage or recovery only |

Prices are versioned commercially. An appointment retains the quoted price and
service duration recorded when it was booked; later catalog changes do not rewrite
the historical obligation.

## 5. Customer lifecycle

1. A customer profile is created after a verified email or phone number is supplied.
2. The customer may remain pay-as-you-go or enroll in one active membership.
3. A customer may book at any location subject to service, qualification, schedule,
   capacity, and booking rules.
4. Service and payment history remain attributable to the same customer even after
   the profile is deactivated.
5. Duplicate profiles may be flagged but are not automatically merged. Cases where
   identity cannot be established require staff investigation.

The customer's statement is recorded faithfully but does not overwrite operational
facts. Contact details are personally identifiable information and must not be
placed in general-purpose audit metadata.

## 6. Appointment lifecycle

An appointment begins as `scheduled` after availability is rechecked and the
reservation commits. It may be confirmed, checked in, completed, cancelled, or
marked as a no-show according to `STATE_MACHINES.md`.

Every lifecycle change produces an immutable appointment event. Corrections append
a correction event and updated state; they do not edit or delete the original
event. Cancellation records distinguish the person or system writing the event
from the party that initiated the cancellation.

A reschedule creates a replacement appointment linked to the prior appointment.
The prior appointment is cancelled with reason `rescheduled`, preserving the chain.
An accepted provider transfer changes the assigned provider through an event and
does not by itself cancel the appointment.

## 7. Payment lifecycle

Luma creates a payment obligation for cash-priced appointments and for assessed
fees. The external payment provider authorizes and captures funds; Luma records
provider references and immutable lifecycle events.

A captured payment can have zero or more refunds. Refundable amount is captured
amount minus successful refund amount. An authorization that was never captured
must be voided or allowed to expire, not refunded. Duplicate-payment review is based
on the obligation settled, not merely matching amounts.

Membership-credit settlement and card payment are different tender types. A
membership-covered service can still have a separate card payment for a cash-only
add-on, gratuity, tax, or assessed fee.

## 8. Membership lifecycle and accounting

Luma offers three monthly plans:

| Plan | Monthly price | Monthly grant | Rollover ceiling |
|---|---:|---:|---:|
| Essential | $109 | 1 credit | 3 unconsumed credits |
| Plus | $199 | 2 credits | 6 unconsumed credits |
| Premier | $369 | 4 credits | 12 unconsumed credits |

From January 1, 2026, each monthly grant expires 90 days after its grant timestamp.
The earlier contract used a 60-day expiry. Consumption uses the earliest-expiring
eligible grant first. Credits are integer units and cannot be partially consumed.

Membership balance is derived from immutable ledger entries: grants, consumption,
expiration, correction, and reversal. A balance is never corrected by overwriting a
stored total. Pause stops future monthly grants and billing but does not extend
existing credit expiration. Cancellation stops future renewal; already granted
credits remain available through their original expiry.

## 9. Online booking

Online availability is computed, not stored as a single yes/no fact. A slot is
bookable only when all of the following are true:

- The location is open for the full service interval.
- The service is active and offered online at that location.
- At least one active, location-assigned, qualified provider is scheduled and free.
- Any required room or equipment capacity is available.
- The start time satisfies the service's minimum lead time and maximum booking
  horizon.
- No temporary location, provider, service, or resource block applies.
- Any service-specific customer eligibility rule is satisfied.

Search results are advisory. The system rechecks all constraints atomically when a
customer submits a booking because another customer may take the slot meanwhile.
A failed search and a failed booking attempt are separately recorded.

## 10. Operational audit expectations

Luma retains immutable events for appointment, payment, refund, membership-ledger,
booking-attempt, and administrative configuration activity. Every event has an
event time and a recorded time. Backfilled events retain the original event time and
the later recording time.

Operational events identify the author, originating channel, reason code, and
correlation reference when available. Sensitive values are represented by stable
references or redacted metadata. Historical events, quoted prices, and effective
policies are never silently rewritten.

## 11. Initial case-resolution scope

The initial operational review scope contains:

1. Duplicate captured payment
2. Cancellation-fee dispute
3. Missing or unexpectedly absent appointment
4. Membership-credit discrepancy
5. Online booking unavailable

Package balances, chargebacks, clinical complaints, employee conduct, identity
merges, tax disputes, and fraud are outside this contract and require specialist
staff handling.

