# Gate C Dataset Freeze and Resolvability Review

Status: **Approved September 3, 2026**

Tool and agent implementation must not begin until the frozen data and the
resolvability claims below are accepted or revised.

## Freeze identity

| Field | Value |
|---|---|
| Dataset | `luma_business_v1` |
| Generator | `1.0.0` |
| Seed | `20260903` |
| Reference time | `2026-09-01T12:00:00Z` |
| Alembic revision | `20260903_0002` |
| Dataset fingerprint | `ab2455c33f90a2089dae8f7fb83ba2713395bdc1d62b93db36b29924a281b14e` |

## Scale

| Domain | Frozen count |
|---|---:|
| Locations / employees / services / customers | 3 / 15 / 25 / 300 |
| Appointments / appointment events | 2,000 / 6,646 |
| Invoices / payments / payment events / refunds | 1,460 / 1,461 / 2,807 / 51 |
| Memberships / ledger entries / allocations | 150 / 563 / 53 |
| Employee schedules / booking attempts / blocks | 9,909 / 205 / 45 |
| Policy documents / versions / sections / links | 5 / 7 / 115 / 34 |

## Review decisions

| Decision | Frozen choice | Review status |
|---|---|---|
| Determinism | UUIDv5 identifiers, fixed seed/clock, logical per-table checksums | Approved |
| Data replacement | Transactional replacement of operational and knowledge rows | Approved |
| Ordinary history | Realistic state distributions and connected event/payment/ledger history | Approved |
| Incident isolation | Canonical incidents are business records; their labels exist only in build manifests | Approved |
| Expected anomalies | Missing event, conflicting initiators, duplicate capture/consumption, and wrongful provider fee are asserted rather than ignored | Approved |
| Policy ingestion | Approved Markdown is parsed into 5 documents, 7 temporal versions, and 115 stable sections | Approved |
| Runtime boundary | Generator and private truth are excluded from the runtime wheel | Approved |
| Resolvability | Five case families are supported with explicit evidence and escalation boundaries | Approved |

## Verification evidence

- Thirty normal data-integrity and reconciliation checks pass.
- Five expected anomaly assertions pass.
- A two-build reproducibility test produces identical row counts, canonical
  references, every logical table checksum, and the dataset fingerprint.
- Provider qualification, location assignment, schedules, location hours, duration,
  and overlap checks pass for all appointments.
- Payment arithmetic/projections, membership allocations/expiry, booking canonical
  explanations, policy date ranges/supersession, and the policy-dependent transfer
  fact all pass.
- No support case, expected resolution, or evaluation label exists in PostgreSQL.

## Gate C approval record

Approved by the project owner on September 3, 2026, without amendment. M4 and M5
must treat this dataset version and fingerprint as immutable input contracts.
