# Luma Wellness Business Specification

This directory describes Luma Wellness as an operating service business. It is the
source of truth for the first synthetic business dataset and deliberately does not
describe agent prompts, graph nodes, or evaluation answers.

## Document map

- `COMPANY.md` - organization, locations, people, services, and customer lifecycle
- `STATE_MACHINES.md` - appointment, payment, membership, and booking-attempt states
- `EVENT_SEMANTICS.md` - actor, initiator, reason, time, and audit interpretation
- `INVARIANTS.md` - business rules and their intended enforcement boundaries
- `DATA_CONTRACT.md` - facts the operational system promises to expose to consumers
- `POLICY_DECISION_TABLE.md` - deterministic policy consistency review
- `policies/` - versioned employee-facing policy documents

## Specification status

Status: **Gate A approved September 3, 2026**

Proposed dataset contract name after approval: `luma_business_v1`.

The specification is frozen only after Gate A approval. Later schema and synthetic
records must implement the approved business rather than silently changing these
rules to make case resolution easier.

## Deliberate scope decisions

- Luma operates in Indianapolis, Chicago, and Denver. Multiple timezones are part of
  normal operations, and policy notice windows use the appointment location's local
  time.
- The first resolution scope contains duplicate payments, cancellation-fee
  disputes, missing appointments, membership-credit discrepancies, and online
  booking availability.
- Ambiguous or insufficient evidence is a condition across every family, not a
  separate business issue type.
- Packages are not part of `luma_business_v1`. They can be added in a later contract
  version without weakening the five initial families.
- A complaint is an allegation. Operational records and effective policy establish
  what happened and what the business should do.
