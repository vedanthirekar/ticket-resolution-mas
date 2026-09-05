# Interview Presentation Narrative

## Thesis

The project is not “ticket to LLM answer.” It tests whether a bounded agent workflow
can reproduce the evidence gathering, policy interpretation, peer review, and
approval boundaries of a real service-operations team.

## Suggested story

1. **Problem:** support decisions require facts spread across bookings, payments,
   memberships, configuration, audit history, and time-versioned policy.
2. **Data-first design:** the organization schema and frozen synthetic operational
   history came before agent behavior; evaluation truth is isolated from runtime.
3. **Agent architecture:** a manager owns the case, an investigator uses scoped
   read-only tools, a knowledge component performs filtered hybrid retrieval, and a
   verifier challenges the exact proposal.
4. **Why a bounded loop:** only policy can request one missing evidence lookup. This
   captures realistic follow-up without unbounded agent chatter.
5. **Safety:** deterministic gates decide whether the result auto-resolves, waits for
   approval, or requires investigation. Model confidence is not a security boundary.
6. **Reliability:** intake, jobs, artifacts, approvals, checkpoints, and actions are
   durable; retries and idempotency handle process failure.
7. **Evaluation:** 60 versioned cases measure stage-level and end-to-end correctness,
   escalation behavior, retrieval, forbidden actions, cost, and latency.
8. **Tradeoff:** multi-agent structure costs latency/tokens but creates bounded tool
   authority, inspectable artifacts, and component-level failure attribution. A
   single-agent baseline is deferred until the main system has reliable measurements.
9. **Production boundary:** show what is real, what is mocked, and what must change
   for multi-tenant deployment.

## Questions to invite

- Why is the verifier separate from the proposal generator?
- Why PostgreSQL/pgvector instead of MongoDB plus a vector service?
- When does the loop stop, and who decides missing evidence?
- What prevents cross-customer access or a duplicate refund?
- What happens if the worker crashes after approval?
- Which metrics block a release, and why is model confidence absent?
- What would you replace first at 100,000 cases per day?

The strongest answer is usually a concrete artifact, invariant, trace, or test—not a
framework name.
