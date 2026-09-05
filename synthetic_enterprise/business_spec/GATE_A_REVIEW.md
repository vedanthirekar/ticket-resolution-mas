# Gate A Business Specification Review

Status: **Approved September 3, 2026**

Schema work must not begin until the choices below are accepted or revised.

## Proposed decisions

| Decision | Proposal | Why it matters downstream | Review status |
|---|---|---|---|
| Operating footprint | Indianapolis, Chicago, and Denver | Creates real timezone, catalog, hours, and capacity variation | Approved |
| Initial support scope | Five families: duplicate payment, cancellation fee, missing appointment, membership credit, online booking | Keeps the first dataset deep and measurable | Approved |
| Package products | Excluded from v1 | Avoids an unused ledger and additional policy surface | Approved |
| Cancellation v2 | Free at 24+ hours; otherwise 50% capped at $80 | Establishes exact fee math and temporal cases | Approved |
| No-show v2 | Full quoted primary service capped at $150 after 15-minute grace | Separates late cancellation from no-show | Approved |
| Provider transfer | Accepted qualified transfer fulfilled within 30 minutes remains a fulfilled service | Creates a legitimate policy-dependent supplemental evidence path | Approved |
| Historical policy | Cancellation threshold changed from 48 hours/$60 on July 1, 2025 | Tests effective-time policy selection | Approved |
| Membership plans | 1/2/4 monthly credits, integer consumption, FIFO allocation | Makes ledger correctness deterministic | Approved |
| Membership expiry | 60 days before 2026; 90 days for grants from 2026 | Tests terms-version selection without rewriting old grants | Approved |
| Mutation control | Explanation can close read-only; every mutation needs operations approval | Defines the product safety boundary | Approved |
| Insufficient evidence | Route directly to human investigation; no customer-information loop in v1 | Keeps workflow bounded and honest | Approved |
| Identity ambiguity | Never auto-merge/select duplicate customer profiles | Prevents acting on the wrong customer | Approved |

## Review evidence

- Company profile contains exactly 3 locations, 15 employees, and 25 services.
- Appointment, payment, membership, and booking-attempt lifecycles are explicit.
- Event author and initiating party have independent controlled vocabularies.
- Thirty-five business invariants have named enforcement boundaries.
- Five policies span seven versioned documents with stable section identifiers.
- Cancellation and membership each have contiguous historical/current versions.
- The policy decision table cites only existing policy sections.
- Automated data-integrity tests enforce entity counts, policy metadata, section
  uniqueness, version intervals, and decision-table citations.

## Gate A approval record

- Approval date: September 3, 2026
- Approval basis: user approved the M1 draft without amendments
- Approved contract name: `luma_business_v1`
- Content fingerprint: to be recorded with the frozen M3 dataset manifest
