# Luma Wellness Policy Corpus

These documents are Luma's controlled internal operating-policy corpus. They state
the rules, decision authority, exceptions, and record requirements used by
operations employees. A policy version is selected using the business event time
and its scope, not the date on which a support case is opened.

The corpus deliberately separates four kinds of material:

- **Operating policies (`POL-*`)** define mandatory business rules and controls.
- **Customer terms** are plain-language summaries presented during booking or
  enrollment; they do not replace the approved internal policy.
- **Standard operating procedures (SOPs)** tell employees how to investigate and
  apply a policy without changing the policy rule.
- **Decision and evaluation artifacts** test consistency but are not policy and are
  never supplied to the runtime policy-retrieval system.

Only the top-level `POL-*.md` files in this directory are loaded into the runtime
knowledge store. `POLICY_DECISION_TABLE.md` remains a business-review artifact
outside the retrievable policy corpus.

| Policy ID | Versions | Area |
|---|---|---|
| POL-CAN | v1, v2 | Cancellation and no-show fees |
| POL-PAY | v1 | Payments, duplicate captures, and refunds |
| POL-MEM | v1, v2 | Membership credit grants and accounting |
| POL-BOOK | v1 | Online booking and appointment-record handling |
| POL-ADJ | v1 | Operational corrections and approval |

Package policy is deliberately absent because packages are outside the
`luma_business_v1` contract.

## Document-control conventions

Every controlled policy identifies its owner, approver, classification, audience,
approval date, review cycle, effective interval, scope, and revision history.
Policy owners review documents annually and whenever a material product, legal, or
operational change occurs. Superseded versions remain available for historical
decisions and must not be silently edited to change the rule that applied at the
time of an event.

References such as `POL-CAN-v2#3.2` are stable citations. Editorial improvements
may clarify a rule, but a material change to a decision threshold, fee, entitlement,
scope, or authority requires a new effective policy version.
