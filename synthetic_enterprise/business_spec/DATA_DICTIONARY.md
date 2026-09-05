# Luma Wellness Data Dictionary

Status: Draft for Gate B schema review

This dictionary describes migration `20260903_0002`. PostgreSQL contains only the
`business` and `knowledge` domains at this milestone. Case-management, workflow,
model-run, and evaluation data are intentionally absent.

## 1. Conventions

- Every table has a UUID `id` generated internally.
- Operationally referenced entities also have a unique stable `public_reference`.
- Mutable projections have `created_at` and `updated_at`; append-only history has
  `created_at` or separate `occurred_at` and `recorded_at` fields.
- Money uses integer cents plus a three-character ISO currency.
- Instants use timezone-aware timestamps. Local policy calculations use the linked
  location's IANA timezone.
- Controlled strings have database check constraints. They are not native enums so
  vocabularies can evolve through ordinary migrations.
- JSONB is reserved for variable metadata and eligibility/scope expressions. Core
  identifiers, statuses, actors, amounts, and timestamps remain typed columns.

## 2. Organization and catalog

| Table | Purpose | Important columns and constraints |
|---|---|---|
| `business.locations` | Current studio projection | unique `public_reference`; `name`; IANA `timezone`; three-character `currency`; `active` |
| `business.location_business_hours` | Versioned weekly opening interval | location FK; `day_of_week` 0–6; `opens_at < closes_at`; effective dates; unique location/day/start |
| `business.employees` | Current workforce projection | unique reference; display name; role; home-location FK; active flag |
| `business.employee_locations` | Effective location assignment | employee/location FKs; non-inverted dates; unique employee/location/start |
| `business.services` | Versioned-by-record service catalog projection | unique reference; category; nonnegative duration/price; positive duration for non-add-ons; optional positive credit cost; qualification and resource codes |
| `business.location_services` | Effective catalog offering at a location | location/service FKs; offered flag; optional nonnegative price override; effective dates |
| `business.employee_services` | Effective provider qualification for a service | employee/service FKs and effective dates |
| `business.employee_schedules` | Concrete availability or block intervals | employee/location FKs; timezone-aware range; `available` or `blocked`; end after start |
| `business.customers` | Current customer identity projection | unique reference; name; unique optional email/phone; at least one contact channel; verification and active flags |

IANA timezone validity, provider qualification at an appointment instant, and
cross-table schedule coverage are transaction/generator rules rather than simple
row constraints.

## 3. Appointments and history

| Table | Purpose | Important columns and constraints |
|---|---|---|
| `business.appointments` | Current reservation projection | unique reference; required customer/location/service/employee FKs; optional unique predecessor; start/end; historical quote and credit cost; status; channel; cancellation projection |
| `business.appointment_events` | Authoritative immutable appointment history | unique reference; appointment FK; event type; actor and separate initiating party; reason; occurred/recorded times; channel; correlation/external/causation references; JSONB metadata |

Appointment statuses are `scheduled`, `confirmed`, `checked_in`, `completed`,
`cancelled`, and `no_show`. Valid transitions are enforced by the appointment
transaction service and generator validation; the row constraint rejects unknown
states.

The current cancellation fields are derived conveniences. Cancellation causation is
established from the event stream, including correction events—not from the current
row or complaint language alone.

## 4. Billing

| Table | Purpose | Important columns and constraints |
|---|---|---|
| `business.invoices` | Current payment obligation projection | unique reference; customer and optional appointment; state; nonnegative total; currency |
| `business.invoice_items` | Itemized obligation truth | unique reference; invoice and optional appointment/service; constrained item type; description; positive quantity; nonnegative amount; currency |
| `business.payments` | Current payment-attempt projection | unique reference; invoice/customer; shared `obligation_reference`; lifecycle state; tender; intended/authorized/captured/refunded amounts; processor and idempotency keys |
| `business.payment_events` | Authoritative provider/internal payment history | unique reference; payment; event type/amount; actor; occurred/recorded times; unique processor event per payment; correlation and JSONB metadata |
| `business.refunds` | Refund command and provider-result projection | unique reference; payment; positive amount; pending/succeeded/failed; reason; unique processor and idempotency references; completion time |

`payments.refunded_amount_cents` is a reconciled projection of successful refund
rows. The refund service locks the payment and reserves both pending and succeeded
refund amounts, preventing concurrent requests from exceeding captured funds.
Payment-provider events remain authoritative for successful capture, void, and
refund state.

## 5. Memberships

| Table | Purpose | Important columns and constraints |
|---|---|---|
| `business.membership_plans` | Effective commercial plan terms | plan reference/version date; monthly price; positive grant; rollover ceiling; currency |
| `business.memberships` | Customer enrollment projection | unique reference; customer/plan; lifecycle state and dates; renewal instant; terms policy/version; partial unique index permits at most one active/paused membership per customer |
| `business.membership_ledger` | Authoritative immutable credit history | unique reference; membership; entry type; signed nonzero delta; effective/recorded/expiry times; appointment/source entry; actor/reason/approval/idempotency references |
| `business.membership_credit_allocations` | Explicit grant-to-consumption allocation | consumption and grant ledger FKs; positive quantity; unique pair |

Grant entries are positive; consumption and expiry entries are negative. Reversal
equality, FIFO allocation, available balance, and correction approval are
multi-record service/generator invariants. No balance column is stored.

## 6. Booking configuration and attempts

| Table | Purpose | Important columns and constraints |
|---|---|---|
| `business.booking_settings` | Effective company defaults | nonnegative lead minutes; positive horizon days; effective interval |
| `business.location_service_settings` | Effective location/service override | online flag; optional lead/horizon overrides; resource type/capacity; JSONB eligibility expression; effective interval |
| `business.employee_booking_settings` | Effective employee or employee/service override | nullable service means provider-wide default; nullable online/lead overrides; unique scoped effective record, including a partial index for null service |
| `business.location_resources` | Location equipment/room capacity group | globally unique reference; location; type/name; positive capacity; active flag |
| `business.booking_blocks` | Temporary restriction | one or more location/employee/service/resource FKs; timezone-aware interval; reason |
| `business.booking_attempts` | Submitted booking transaction history | unique reference/idempotency key; correlation; customer/requested scope/time/channel; state/reason; committed state requires one unique appointment |

Effective setting precedence is:

```text
company default
  -> location/service override
  -> employee-wide override
  -> employee/service override
  -> temporary block (always restrictive)
```

An override changes only fields for which it contains a value. A more-specific
record cannot make a location-unsupported service valid. Resource capacity,
provider busy intervals, and appointment duration are evaluated after settings.

## 7. Cross-domain audit

| Table | Purpose | Important columns and constraints |
|---|---|---|
| `business.audit_events` | Append-only administrative/configuration audit not already represented by a domain event | unique reference; target type/reference; action; actor; occurred/recorded times; correlation; JSONB metadata |

Appointment, payment, and membership events are not duplicated here. This table is
authoritative for configuration changes, identity administration, and other
cross-domain operations only.

## 8. Policy corpus

| Table | Purpose | Important columns and constraints |
|---|---|---|
| `knowledge.policy_documents` | Stable policy family | unique `policy_id`; title; indexed area |
| `knowledge.policy_versions` | Temporal policy version | document/version unique pair; effective dates; draft/active/superseded; JSONB scope; supersession link; unique source and checksum; publication time |
| `knowledge.policy_sections` | Retrievable stable section | version; globally unique section ID; optional parent; heading/body/order/checksum; generated English `tsvector` with GIN index |
| `knowledge.policy_section_links` | Explicit inter-section relationship | source/target; references/exception/supersedes/related type; no self-link; unique edge |

Policy embeddings are intentionally absent. The embedding model and vector dimension
are still open decisions; an embedding column and index will be introduced with the
hybrid retrieval milestone rather than selecting a dimension accidentally.

## 9. Authoritative versus derived fields

| Fact | Authoritative source | Derived/projection |
|---|---|---|
| Appointment transition and initiator | `appointment_events` | `appointments.status`, cancellation summary |
| Payment provider result | `payment_events` | `payments.status` and lifecycle amount projections |
| Refund transaction result | refund provider result plus payment event | `refunds.status`, payment refunded projection |
| Membership balance | sum and allocation of `membership_ledger` | computed as-of balance; no stored balance |
| Booking transaction result | `booking_attempts` and committed appointment FK | UI notification state |
| Online availability | settings, schedules, qualifications, appointments, resources, blocks | computed slots |
| Policy text | versioned source document and checksums | section search vector |

## 10. Query-oriented indexes

- Appointments: `(customer_id, scheduled_start)` and `(employee_id, scheduled_start)`
- Appointment history: `(appointment_id, occurred_at, id)`
- Invoices/payments: customer or invoice plus creation time; obligation reference
- Payment events: `(payment_id, occurred_at, id)`
- Refunds: `(payment_id, status)`
- Membership ledger: `(membership_id, effective_at, id)`
- Schedules and blocks: scope with time range
- Booking attempts: customer/creation and correlation reference
- Policy corpus: policy area plus GIN full-text search vector

