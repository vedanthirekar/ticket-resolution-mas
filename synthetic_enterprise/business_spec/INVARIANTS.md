# Business Invariants and Enforcement Boundaries

Status: Gate A approved September 3, 2026

Enforcement layers are additive. Database constraints protect local structural
truth; transaction rules protect multi-record operations; generator validation
proves synthetic histories are coherent; evidence checks prevent unsupported case
decisions.

| ID | Invariant | Primary enforcement | Additional enforcement |
|---|---|---|---|
| INV-001 | Every appointment has exactly one customer, location, primary service, and assigned provider | Database constraint | Generator validation |
| INV-002 | Assigned provider is active, assigned to the location, and qualified for the service at appointment time | Transaction/service rule | Generator validation, evidence check |
| INV-003 | Appointment interval lies inside location hours and provider schedule unless an explicit anomaly exists | Transaction/service rule | Generator validation, evidence check |
| INV-004 | Provider and capacity-bound resource intervals cannot overlap beyond capacity | Transaction/service rule | Generator validation |
| INV-005 | Appointment current state is consistent with its accepted event sequence | Transaction/service rule | Generator validation, evidence check |
| INV-006 | Terminal appointments cannot receive normal lifecycle transitions | Transaction/service rule | Generator validation |
| INV-007 | A rescheduled appointment links to one distinct replacement; the prior reservation remains historical | Database constraint | Transaction/service rule |
| INV-008 | Cancellation event records author and initiating party independently | Database constraint | Generator validation, evidence check |
| INV-009 | Fee obligation links to the appointment or invoice item that created it | Database constraint | Evidence check |
| INV-010 | Monetary amounts are integer cents, non-negative where defined, with ISO currency | Database constraint | Generator validation |
| INV-011 | A payment settles one identified obligation; multiple attempts may share that obligation | Database constraint | Evidence check |
| INV-012 | Authorized, captured, and refunded amounts follow the payment lifecycle arithmetic | Database constraint | Transaction/service rule, generator validation |
| INV-013 | Successful cumulative refunds never exceed captured amount | Transaction/service rule | Database constraint, evidence check |
| INV-014 | An uncaptured authorization is voided, not refunded | Transaction/service rule | Evidence check |
| INV-015 | Provider event references are unique for idempotent webhook processing | Database constraint | Transaction/service rule |
| INV-016 | Refund idempotency key cannot create two refunds for one approved action | Database constraint | Transaction/service rule |
| INV-017 | A customer has at most one active or paused membership at a time | Database constraint | Transaction/service rule |
| INV-018 | Membership balance is derived from immutable ledger entries, never directly overwritten | Transaction/service rule | Generator validation, evidence check |
| INV-019 | Credit consumption never exceeds eligible unexpired grants | Transaction/service rule | Generator validation |
| INV-020 | Consumption allocates earliest-expiring eligible credits first | Transaction/service rule | Generator validation, evidence check |
| INV-021 | Reversal references one existing ledger entry and has equal opposite quantity | Database constraint | Transaction/service rule, generator validation |
| INV-022 | A correction carries a structured reason and approving employee | Database constraint | Evidence check |
| INV-023 | Credit grant expiry follows the policy effective at grant time | Transaction/service rule | Generator validation, evidence check |
| INV-024 | Online booking requires active location-service configuration | Transaction/service rule | Evidence check |
| INV-025 | Online booking requires location hours, qualification, provider availability, resource capacity, lead time, horizon, and customer eligibility | Transaction/service rule | Generator validation, evidence check |
| INV-026 | A committed booking attempt references exactly one appointment | Database constraint | Transaction/service rule, generator validation |
| INV-027 | Reusing a booking idempotency key returns the original result | Database constraint | Transaction/service rule |
| INV-028 | Quoted appointment price and duration do not change when the service catalog changes | Transaction/service rule | Generator validation, evidence check |
| INV-029 | Event references are unique and event history is append-only | Database constraint | Transaction/service rule |
| INV-030 | Event time and recorded time are timezone-aware; local rules use the location timezone | Database constraint | Generator validation, evidence check |
| INV-031 | A policy section has stable policy/version/section identity and an unambiguous effective interval | Database constraint | Corpus validation, evidence check |
| INV-032 | Policy versions for the same scope do not overlap unless explicit precedence is recorded | Corpus validation | Evidence check |
| INV-033 | A support outcome cites existing operational evidence and policy sections | Transaction/service rule | Evidence check |
| INV-034 | Missing, contradictory, or unavailable required evidence cannot support a definitive corrective action | Evidence check | - |
| INV-035 | Package records and package outcomes are absent from the v1 contract | Generator validation | - |

## Anomaly policy

Synthetic data may include deliberate missing or conflicting evidence to test
investigation behavior. Such records must be declared in a hidden anomaly manifest
and must not bypass structural database constraints. Deliberate anomalies are
business-level incompleteness or contradiction, such as a missing cancellation
event or competing corrected/uncorrected facts, rather than physically impossible
foreign keys.
