# Policy Decision Consistency Table

Status: Gate A approved September 3, 2026

This table is a business-review artifact. It validates that policy documents lead
to consistent results. It is not an operational answer table and will not be placed
in runtime retrieval storage.

## Cancellation and no-show

| ID | Situation | Result | Required facts | Governing section |
|---|---|---|---|---|
| CAN-01 | Provider or business initiated cancellation; no accepted fulfilled replacement | Customer owes no cancellation fee; refund or waive one if assessed | initiator, fee, replacement/transfer fulfillment, event time | POL-CAN v2 §4.1 |
| CAN-02 | Provider became unavailable; customer accepted qualified replacement and service completed | Service obligation remains valid; no cancellation refund is due merely from reassignment | transfer acceptance, provider history, completion, payment item | POL-CAN v2 §4.2 |
| CAN-03 | Customer cancelled at least 24 hours before start under v2 | No cancellation fee | initiator, cancellation time, scheduled start, location timezone | POL-CAN v2 §3.1 |
| CAN-04 | Customer cancelled less than 24 hours before start under v2 | Late fee is 50% of quoted primary-service price, capped at $80 | same as CAN-03 plus quoted price and fee item | POL-CAN v2 §3.2 |
| CAN-05 | Customer no-show under v2 | No-show fee is quoted primary-service price, capped at $150 | no-show event, scheduled start, price, fee item | POL-CAN v2 §3.3 |
| CAN-06 | Cancellation is caused by verified emergency exception | Fee waived once documentation is accepted by operations | initiator, timing, exception approval | POL-CAN v2 §5.1 |
| CAN-07 | Event occurred under v1 and customer gave 24–48 hours' notice | v1 applies; $60 late fee may be retained | event time, local notice, effective policy | POL-CAN v1 §3.1–3.2 |
| CAN-08 | Initiating party missing or contradictory | No definitive fee decision; investigate | appointment and complete event/correction history | POL-CAN v2 §6.1 |

## Payments and refunds

| ID | Situation | Result | Required facts | Governing section |
|---|---|---|---|---|
| PAY-01 | Two successful captures settle the same obligation and no second item was fulfilled | Later duplicate capture is refundable | capture events, obligation/items, fulfillment, prior refunds | POL-PAY v1 §3.1 |
| PAY-02 | Matching charges settle different appointments, fees, add-ons, or gratuities | Charges are distinct; explain, do not refund as duplicate | itemized obligations and fulfillment | POL-PAY v1 §3.2 |
| PAY-03 | One entry is authorized but not captured | It is an authorization hold; void if still actionable, never refund | provider lifecycle state and references | POL-PAY v1 §4.1 |
| PAY-04 | Duplicate capture already fully refunded | Explain prior refund; no second refund | capture and successful refund totals | POL-PAY v1 §5.2 |
| PAY-05 | Proposed refund exceeds refundable amount | Reject action and investigate discrepancy | captured and successful refund totals | POL-PAY v1 §5.1 |
| PAY-06 | Provider status is unavailable after bounded retry | Do not infer success; investigate | tool/source failure record | POL-PAY v1 §6.1 |

## Membership credits

| ID | Situation | Result | Required facts | Governing section |
|---|---|---|---|---|
| MEM-01 | Completed eligible service consumed correct credit quantity FIFO | Consumption retained | service credit cost, completion, grants, allocations | POL-MEM v2 §4.1 |
| MEM-02 | Business/provider cancellation caused service not to be fulfilled but credits were consumed | Reverse consumption or restore credits | event initiator, completion absence, ledger source | POL-MEM v2 §5.1 |
| MEM-03 | Customer late-cancelled/no-showed and policy permits credit forfeiture | Consumption retained | cancellation result, terms, ledger association | POL-MEM v2 §5.2 |
| MEM-04 | Grant expired 90 days after grant under v2 | Expiration retained | grant time, expiry, terms version, consumption allocation | POL-MEM v2 §3.2 |
| MEM-05 | Grant before 2026 expired after 60 days under v1 | v1 expiration retained | grant time, expiry, terms version | POL-MEM v1 §3.2 |
| MEM-06 | Ledger balance differs from cached/displayed balance | Ledger controls; correct projection, not ledger | full ledger and projection timestamp | POL-MEM v2 §6.1 |
| MEM-07 | Ledger entry is missing, duplicated, or has broken reversal chain | Do not overwrite balance; investigate and append approved correction | complete ledger slice and source records | POL-MEM v2 §6.2 |

## Missing appointment

| ID | Situation | Result | Required facts | Governing section |
|---|---|---|---|---|
| APT-01 | Original was rescheduled and linked replacement is active | Explain replacement appointment | original/replacement records and reschedule events | POL-BOOK v1 §6.1 |
| APT-02 | Submitted booking attempt was rejected and no appointment committed | Explain recorded rejection reason | booking attempt and config evidence | POL-BOOK v1 §5.2 |
| APT-03 | Submitted attempt failed technically with no appointment | Propose staff-assisted recovery; do not assert reservation existed | failed attempt and absence of committed reference | POL-BOOK v1 §5.3 |
| APT-04 | Payment exists but neither obligation nor appointment relationship is clear | Investigate; payment alone does not prove a booking | payment item, attempts, appointment search | POL-BOOK v1 §6.2 |
| APT-05 | Identity maps to multiple plausible customer profiles | Investigate; do not merge or choose silently | identity-match results | POL-BOOK v1 §6.3 |

## Online booking availability

| ID | Situation | Result | Required facts | Governing section |
|---|---|---|---|---|
| BKG-01 | No qualified free provider covers the full interval | Legitimately unavailable | service qualifications, assignments, schedules, busy intervals | POL-BOOK v1 §3.1 |
| BKG-02 | Location closed or service interval crosses close | Legitimately unavailable | local hours/closure and duration | POL-BOOK v1 §3.2 |
| BKG-03 | Location does not offer service online | Explain configuration restriction | effective location-service config | POL-BOOK v1 §3.3 |
| BKG-04 | Lead time, horizon, eligibility, or resource capacity fails | Explain applicable restriction | effective rule and requested parameters | POL-BOOK v1 §3.4–3.7 |
| BKG-05 | Every required condition is satisfied but engine returned no slots | Configuration or technical discrepancy; propose operational review | complete availability inputs and attempt/search result | POL-BOOK v1 §5.3 |
| BKG-06 | One required availability source is missing/unavailable | Cannot diagnose definitively; investigate | source failure or missing configuration | POL-BOOK v1 §7.1 |

## Adjustments and approval

| ID | Situation | Result | Required facts | Governing section |
|---|---|---|---|---|
| ADJ-01 | Outcome is a supported explanation with no mutation | May be completed without a corrective transaction | cited facts and policy | POL-ADJ v1 §3.1 |
| ADJ-02 | Refund, fee waiver, membership correction, or booking/config mutation proposed | Authorized operations approval required before execution | verified proposal, target, before-state, evidence | POL-ADJ v1 §3.2 |
| ADJ-03 | Approved command is retried | Same idempotency key returns original result | approval/action/idempotency references | POL-ADJ v1 §4.1 |
| ADJ-04 | Evidence conflicts or required evidence/policy is unavailable | Human investigation; no mutation | missing/contradiction/source details | POL-ADJ v1 §5.1 |

## Cross-table consistency findings

- Cancellation fees are decided from cancellation policy; payment policy governs
  whether and how a captured amount can be refunded.
- A provider reassignment is not a cancellation. Fulfillment facts determine whether
  the original service obligation remains valid.
- Membership-credit restoration uses ledger rules even when the root cause is an
  appointment cancellation.
- Recorded booking rejection can support an explanation; an unexplained lack of
  results requires complete availability inputs before it can be called a defect.
- No rule authorizes a mutation when identity, target, amount/quantity, or effective
  policy is unresolved.
