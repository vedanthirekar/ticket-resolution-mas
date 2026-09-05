# Gate B Schema and Policy Storage Review

Status: **Approved September 3, 2026**

M3 synthetic-data generation must not begin until this schema contract is accepted
or revised.

## Proposed schema decisions

| Decision | Implemented choice | Rationale | Review status |
|---|---|---|---|
| Database boundaries | Only `business` and `knowledge` schemas exist | Preserves the fiction of an existing operational system before the case-resolution product | Approved |
| Entity identity | UUID internal primary keys plus stable public references | Efficient relational joins without exposing storage identity to tools or users | Approved |
| Controlled vocabularies | Checked strings rather than native PostgreSQL enums | Strong validation with simpler vocabulary migrations | Approved |
| Operational history | Append-only domain events plus current projections | Supports investigation, replay, audit, and efficient reads | Approved |
| Cancellation causation | Event author and initiating party are separate required fields | Prevents an employee recording a call from being mistaken for the canceller | Approved |
| Payment obligation | Itemized invoices plus a shared payment obligation reference | Duplicate captures are established by what they settle, not amount similarity | Approved |
| Refund safety | Payment row lock plus pending/succeeded reservation accounting | Prevents concurrent over-refunds; database also rejects invalid local amounts | Approved |
| Membership balance | No stored balance; immutable ledger plus explicit credit allocations | Makes balance provenance and corrections auditable | Approved |
| Booking explanation | Layered company, location/service, employee, resource, block, and attempt data | Retains enough facts to explain why a slot was unavailable | Approved |
| General audit | Only cross-domain/configuration events; no duplicate domain history | Avoids competing authoritative event streams | Approved |
| Policy search | Generated PostgreSQL full-text vector and GIN index now | Enables lexical retrieval without an extra system | Approved |
| Policy embeddings | Column/dimension deferred to retrieval milestone | Avoids coupling storage to an unselected embedding model | Approved |
| Packages | No package tables | Enforces the Gate A v1 scope decision | Approved |

## Implemented database surface

- 31 tables across the two approved schemas
- UUID foreign-key graph with stable external references
- Lifecycle, amount, range, status, idempotency, and effective-date constraints
- Query-oriented indexes for customer timelines, event histories, payments, ledger,
  schedules, booking attempts, and policy full-text search
- Standalone Alembic revision `20260903_0002`
- SQLAlchemy models organized by business domain
- Transaction service that serializes and validates refund reservation

## Verification evidence

- Full downgrade to an empty database and upgrade to head succeeds.
- Database table inventory exactly equals declared SQLAlchemy metadata.
- Alembic autogenerate comparison reports no schema drift.
- A connected representative transaction inserts organization, appointment/event,
  invoice/payment/refund, membership/ledger/allocation, and policy/version/section
  records.
- Invalid zero-duration primary service is rejected by PostgreSQL.
- Refund above the remaining captured amount is rejected by the transaction service.
- The full non-model suite passes against PostgreSQL.

## Known later enforcement work

Some invariants require multiple rows or temporal interpretation and therefore do
not belong in row check constraints. M3 validators and later transaction services
must enforce provider qualification, schedule/capacity overlap, appointment state
transitions, invoice/payment currency agreement, policy-version non-overlap, FIFO
credit consumption, reversal equality, and projection reconciliation.

## Gate B approval record

- Approval date: September 3, 2026
- Approval basis: user approved the M2 implementation without amendments
- M3 dataset target: `luma_business_v1`
