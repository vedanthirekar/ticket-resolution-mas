# Corrective Golden Cases

These cases are the acceptance gate for the core workflow. Live-model quality is measured only
after the same paths pass with a deterministic model double.

| Scenario | Claimed category | Identifier supplied? | Expected category | Expected disposition | Expected outcome/reason |
|---|---|---:|---|---|---|
| Provider cancelled and charged fee | cancellation fee | no | cancellation fee | human approval | refund cancellation fee |
| Customer cancelled late | cancellation fee | no | cancellation fee | auto resolve | retain cancellation fee |
| Valid no-show fee | cancellation fee | no | cancellation fee | auto resolve | retain no-show fee |
| Duplicate capture | payment | no | duplicate payment | human approval | refund duplicate payment |
| Two legitimate equal charges | payment | no | duplicate payment | auto resolve | explain distinct charges |
| Authorization hold | payment | no | duplicate payment | auto resolve | explain authorization hold |
| Duplicate membership consumption | membership credits | no | membership credits | human approval | restore one credit |
| Booking blocked by configuration | online booking | no | online booking unavailable | auto resolve | explain booking restriction |
| Missing cancellation audit event | cancellation fee | yes | cancellation fee | human investigation | required evidence missing |
| Conflicting cancellation events | cancellation fee | yes | cancellation fee | human investigation | conflicting evidence |
| Booking platform technical failure | online booking | no | online booking unavailable | human investigation | technical failure unsupported for automation |
| Unsupported complaint | other | no | unknown | human investigation | unsupported category |

## Non-negotiable checks

- Customer-selected category is a hint and may be corrected.
- A missing appointment/payment/booking reference does not itself trigger escalation.
- The investigator discovers records, observes results, and uses only returned identifiers.
- Placeholders and invented identifiers are blocked before tools execute.
- Every mutation pauses for human approval; ambiguous or conflicting evidence fails closed.
- Simulator and manual intake use the same product contract. Simulator scenario labels remain local.
