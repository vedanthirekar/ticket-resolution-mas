# Interview Presentation: Polished Content

This version is designed for a 45-minute AI engineering interview slot: 35 minutes
of presentation and narrated demonstration, followed by about 10 minutes of
questions. The slide copy is intentionally short; the detail belongs in the spoken
narrative and the demo.

## Core message

> Luma is not a "ticket in, LLM answer out" demo. It is a bounded, evidence-driven
> workflow that reproduces how a service-operations team investigates a case,
> applies time-correct policy, reviews a proposed decision, and controls risky
> actions.

## Recommended deck

### 35-minute run of show

| Slide | Topic | Target |
|---|---|---:|
| 1 | Title and framing question | 1:00 |
| 2 | The operational problem | 2:30 |
| 3 | Product goal and boundaries | 2:00 |
| 4 | Data-first design | 2:30 |
| 5 | System architecture | 3:00 |
| 6 | One case through the system | 3:30 |
| 7 | Why multiple components | 2:30 |
| 8 | Safety model | 3:30 |
| 9 | Narrated live demo | 5:00 |
| 10 | Evaluation strategy | 2:30 |
| 11 | Current evidence | 2:00 |
| 12 | Failure and iteration story | 2:00 |
| 13 | Key engineering decisions | 1:30 |
| 14 | Production gaps and next steps | 1:00 |
| 15 | Closing | 0:30 |
|  | **Total** | **35:00** |

Treat these as rehearsal checkpoints, not hard cuts. If the demo runs long, shorten
slides 7, 13, and 14 rather than rushing the safety or evaluation sections.

### Slide 1 - Title

**Luma: A Production-Minded AI Case Resolution System**

Evidence-driven investigation, policy reasoning, verification, and human-approved
actions

Vedant Hirekar | AI Engineering Interview

**Say:** "I built Luma to explore a practical question: how do we let an AI system
resolve operational cases without treating model confidence as a safety boundary?"

---

### Slide 2 - The problem

**Support decisions are evidence problems**

- The facts are distributed across bookings, payments, memberships, appointments,
  audit history, and configuration.
- The correct policy depends on the event date, business scope, and case context.
- A plausible answer is not enough: the decision must be traceable, safe, and
  recoverable when something fails.

**Bottom line:** Manual investigation is slow; unconstrained automation is risky.

**Visual:** Show a support case in the center with several source systems around it.

---

### Slide 3 - Product goal and boundaries

**Automate the routine path. Escalate the uncertain path.**

For each case, Luma:

1. gathers customer-scoped operational evidence;
2. retrieves the policy valid on the material event date;
3. proposes and independently verifies a resolution; and
4. resolves, requests approval, or escalates for investigation.

**MVP boundary:** The model never receives a write tool. Every financial or
membership mutation requires human approval and deterministic execution.

---

### Slide 4 - Data-first design

**The data model came before the agents**

- Frozen synthetic business history across customers, locations, employees,
  appointments, bookings, invoices, payments, and memberships
- Versioned policy sections with effective dates and business scope
- Durable artifacts for plans, evidence, retrievals, proposals, verification,
  approvals, actions, and audit history
- Evaluation truth isolated from all runtime-accessible data

**Say:** "The agents operate on a consistent business world. I did not generate
convenient facts after seeing the model's answer."

---

### Slide 5 - System architecture

**Durable workflow around a probabilistic core**

Customer intake / simulator -> FastAPI -> PostgreSQL job queue -> worker ->
LangGraph workflow -> resolution, investigation, or approval

Supporting components:

- PostgreSQL + pgvector: operational facts, policies, artifacts, and audit history
- Next.js operations UI: queue, case workspace, evidence, policy, and approvals
- Structured logs + optional LangSmith traces: stage latency, tokens, failures, and
  case/run references without prompt or complaint bodies

**Visual:** Use the implemented diagram from `docs/ARCHITECTURE.md`. Avoid a generic
cloud-vendor diagram.

---

### Slide 6 - One case through the system

**A bounded, inspectable decision flow**

1. Intake creates an idempotent case and durable job.
2. The manager produces typed investigation objectives.
3. The investigator makes up to eight customer-scoped, read-only tool calls.
4. Hybrid retrieval filters policy by scope and effective date before ranking.
5. Policy may request one supplemental evidence lookup.
6. The manager proposes a grounded resolution.
7. Deterministic checks and an independent verifier challenge the proposal.
8. The system resolves, escalates, or pauses for approval.

**Say:** "There is no open-ended agent conversation. The loop is explicit and has a
hard stop."

---

### Slide 7 - Why multiple components?

**Separation creates useful boundaries**

| Component | Owns | Cannot do |
|---|---|---|
| Case manager | Plan, synthesize, propose | Execute a mutation |
| Investigator | Gather provenanced operational evidence | Write business data |
| Policy component | Retrieve and assess time-correct rules | Invent operational facts |
| Verifier | Challenge support, gaps, and contradictions | Call tools or repair its own input |
| Action executor | Revalidate and execute an approved command once | Change the approved command |

**Tradeoff:** More calls increase latency and token cost, but the boundaries make
authority explicit and failures attributable to a stage.

---

### Slide 8 - Safety model

**Model output is a proposal, not authority**

- Trusted customer scope is injected by the server, not supplied by the model.
- Investigation tools are fixed, read-only, and customer-scoped.
- Typed schemas validate every probabilistic boundary.
- Evidence and policy citations are checked before semantic verification.
- Disposition is deterministic: auto-resolve, human approval, or investigation.
- Approved actions are frozen, reauthorized, revalidated under lock, and executed
  with an idempotency key.
- Missing, conflicting, stale, cross-customer, or malformed inputs fail closed.

**Visual:** Proposal -> deterministic checks -> verifier -> disposition -> approval
-> revalidation -> idempotent execution.

---

### Slide 9 - Demo: make the controls visible

**Demo one case end to end**

1. Submit a cancellation-fee dispute.
2. Open the case workspace and show the investigation plan.
3. Show the exact source records and effective policy section.
4. Show the proposal and verifier output.
5. If the outcome is a mutation, approve the frozen action.
6. Show the receipt and audit trail after the worker resumes.

**Narrate artifacts, not screens:** what was observed, which policy applied, why the
disposition was chosen, and what prevented duplicate or stale execution.

---

### Slide 10 - Evaluation strategy

**Evaluate behavior, not eloquence**

- 60 versioned cases with development and untouched held-out splits
- Deterministic graders for classification, decision, disposition, evidence,
  policy/tool recall, and exact action arguments
- Safety metrics for unauthorized and duplicate execution
- Fault injection for tool outages; integration tests for approval, retry,
  stale-state, and crash-resume behavior
- Every report records dataset, business data, model, prompts, tools, graph, latency,
  tokens, and cost configuration

**Release gates:** 0% unauthorized actions, 0% duplicate executions, >=90% held-out
decision accuracy, and >=95% unsafe-case escalation recall.

---

### Slide 11 - What the evidence says today

**Strong engineering evidence; model-quality validation is still open**

- PostgreSQL retrieval evaluation: 16/17 recall@5 (94.12%)
- Full PostgreSQL-backed test suite: 67 passing tests
- Ruff, strict mypy, Next.js checks, production build, and CI: passing
- One live-model development smoke case passed all applicable deterministic graders
- Full development and untouched held-out model runs remain pending

**Say:** "A one-case smoke test proves the path can work; it does not establish an
accuracy rate. I would not promote this configuration until Gate E is complete."

---

### Slide 12 - A failure that improved the design

**Tracing exposed boundary failures**

Observed failures included provider 503s/timeouts, invalid structured output, and a
proposal that had the right evidence but an unsupported action.

What changed:

- added bounded, stage-level retries for transient provider failures;
- moved customer scope and policy effective-date selection out of model control;
- replaced an untyped action dictionary with a constrained command schema; and
- kept deterministic escalation when a proposal is unsupported.

**Takeaway:** The fail-closed path worked, and the traces showed which boundary to
tighten. Provider availability and model-quality errors are tracked separately.

---

### Slide 13 - Key engineering decisions

**Where I deliberately constrained autonomy**

- One supplemental evidence pass, not an unbounded agent debate
- PostgreSQL as the system of record; checkpoints store execution position only
- Human approval for every MVP mutation, regardless of amount
- Independent verifier, because proposal generation and critique are different
  failure modes
- Exact deterministic action grading instead of an LLM judge for safety
- Single-agent baseline deferred until the current architecture has reliable,
  comparable measurements

**Say:** "These are prototype choices, not universal truths. Each one is explicit,
testable, and replaceable when the measurements justify it."

---

### Slide 14 - Production gaps and next steps

**What I would build next**

1. Complete development tuning, freeze the configuration, then run the held-out set.
2. Add real IAM/RBAC, tenant isolation, verified customer identity, and secrets
   management.
3. Replace mock actions with payment/booking integrations using provider-side
   idempotency and reconciliation.
4. Add lease heartbeats, circuit breakers, provider fallback, and production
   monitoring.
5. Benchmark the multi-component workflow against a simpler single-agent baseline
   for accuracy, latency, and cost.

**Current limitation:** This is a production-minded prototype, not a production
deployment.

---

### Slide 15 - Closing

**What this project demonstrates**

- System design around probabilistic components
- Bounded tool use and explicit authority boundaries
- Durable workflows, approvals, retries, and idempotency
- Evaluation with frozen data, exact graders, and honest release gates
- Clear separation between what is implemented, measured, mocked, and still open

**Closing line:** "The core lesson is that trustworthy agentic systems come from the
deterministic system around the model as much as from the model itself."

**Questions**

## Detailed 35-minute speaker guide

These notes are a rehearsal script, not additional slide copy. At a calm interview
pace, including transitions and the live demonstration, they fill approximately 35
minutes. Use your own phrasing so the delivery remains conversational.

### Slide 1 - 1:00

"This project is called Luma. It is a production-minded AI system for resolving
operational customer cases. I use the phrase production-minded deliberately. It is
not deployed as a production service, but I designed the prototype around the
problems that appear once an LLM must interact with real business state: grounding,
authorization, retries, auditability, evaluation, and human approval.

The question I wanted to answer was not simply, 'Can a model respond to a support
ticket?' Models can already produce plausible responses. The harder question is:
can I build a bounded system that gathers the right evidence, applies the right
version of policy, explains its decision, and cannot turn a model mistake into an
unsafe business action? I will show the architecture, walk through a case, explain
the controls, and then be candid about what the evaluation proves and what remains
open."

**Transition:** "To understand the architecture, it helps to start with the work a
human support operator actually performs."

### Slide 2 - 2:30

"A support case initially looks like a language problem because the input is a
customer complaint. In practice, the language is only the starting point. The
decision depends on facts spread across several systems. For a cancellation-fee
dispute, for example, I may need the appointment, the booking, who initiated the
cancellation, the payment record, any prior refund, the customer's membership, the
location, and the policy effective when the event happened.

That creates three distinct risks. First is evidence risk: the model may omit an
important lookup or confuse two records. Second is policy risk: retrieving a
semantically similar paragraph is not enough if it applies to another location or
became effective after the event. Third is action risk: even a reasonable narrative
does not authorize a refund or membership-credit adjustment.

A human operator handles these risks by moving between systems, interpreting
policy, checking exceptions, and asking a colleague to review unusual decisions.
That makes the process slow and inconsistent, but replacing it with one prompt
merely hides those steps inside an opaque model call.

So I reframed the problem as an evidence-backed decision workflow. The complaint is
untrusted input. Operational tables are the source of facts. Versioned policy is the
source of business rules. The model helps plan, interpret, and synthesize, while the
surrounding application controls scope, lifecycle, and execution.

The product opportunity is to automate routine cases and prepare high-quality case
files for the rest. The safety objective is equally important: uncertainty should
be visible and should lead to escalation rather than a confident guess."

**Transition:** "That framing produced a narrower and more testable product goal."

### Slide 3 - 2:00

"For every submitted case, the system has four responsibilities. It gathers
customer-scoped operational evidence. It finds the policy that was valid for the
material event. It creates a grounded proposal and subjects that proposal to an
independent review. Finally, it chooses one of three explicit outcomes.

The first outcome is auto-resolution. This is reserved for safe, read-only results,
such as explaining a charge when the evidence and policy support it. The second is
human approval. If the proposal contains a mutation, such as a refund, the workflow
pauses with one exact command for an operator to approve or reject. The third is
human investigation. Missing evidence, contradictions, unreliable action evidence,
or any safety failure takes this path.

This distinction between approval and investigation is important. Approval means
the system believes it has a complete, verified action proposal but lacks authority
to execute it autonomously. Investigation means the system does not have enough
support for a safe decision.

The main MVP boundary is that the model never receives a write tool. It can propose
an action using a typed schema, but deterministic application code validates,
freezes, authorizes, and eventually executes that action. This gives the prototype a
useful end-to-end path without pretending model output is authority."

### Slide 4 - 2:30

"I built the data model before the agent workflow. That choice made the rest of the
project much more concrete. I created a synthetic wellness business with linked
customers, employees, locations, appointments, bookings, invoices, payments,
memberships, and audit events. The history is frozen and versioned, so a case must be
resolved against a stable business world rather than convenient facts created after
the output is known.

Policy is also modeled as data. Sections have scope and effective dates. Retrieval
therefore begins with deterministic filters for the relevant business area and the
material event date. Vector and lexical ranking happen only after those filters.
This avoids a subtle but common RAG failure: retrieving text that sounds correct but
was not actually applicable.

I separated four kinds of state. Business tables own operational facts. Policy
tables own the rules. Application artifact tables store plans, tool evidence,
retrieval results, proposals, verification, approvals, actions, and audit history.
LangGraph checkpoints store execution position, not the business record. That means
the dashboard and APIs do not need to reverse-engineer internal graph state to tell
an operator what happened.

Evaluation truth is separate again. Expected answers live in versioned evaluation
artifacts that the runtime cannot query. Live evaluation cases enter through the
same intake path as ordinary cases, so the model cannot identify them or retrieve
their expected outcome.

This data-first approach forced me to define sources of truth and invariants before
tuning prompts. It also made failures reproducible: I can point to the exact source
record, policy version, artifact, and expected behavior for a case."

### Slide 5 - 3:00

"At the system level, a customer or simulator submits a case to FastAPI. Intake is
transactional and idempotent: retrying the same external request does not create a
second case. The API persists both the case and a durable job in PostgreSQL.

A separate worker leases jobs and invokes the LangGraph workflow. I used a database
queue for the prototype because PostgreSQL is already the source of truth and the
required scale does not justify another infrastructure dependency. The lease makes
work recoverable if a process disappears. A production version would add a lease
heartbeat and could move to a dedicated broker when throughput measurements justify
it.

Inside the workflow, model-driven components use read-only operational tools and a
hybrid policy retriever. Every stage writes typed artifacts to PostgreSQL. The graph
can end in a resolved state, a terminal investigation state, or an interrupt while
an exact action waits for human approval.

After an operator records a durable decision, the worker resumes the graph. The
approval HTTP request itself does not perform a refund. That separation prevents a
web request from becoming an unsafe execution boundary and lets the same durable
lifecycle handle retries and crashes.

The Next.js operations UI talks to the API through a server-side BFF using an
HTTP-only cookie. It renders application artifacts such as evidence, policy,
verification, and action intent. It never reads graph checkpoints or evaluation
truth.

For observability, structured logs carry references, stage names, durations, token
counts, and error classes. Optional LangSmith traces provide model-stage detail.
Complaint bodies, prompts, model responses, secrets, and customer details are
excluded from logs. Rich evidence stays in access-controlled database records.

The architectural theme is durability around a probabilistic core. A model call can
fail or be retried without losing the case lifecycle, and the business state remains
authoritative outside the graph."

### Slide 6 - 3:30

"Here is one case in more detail. Intake validates the request, binds a claimed
customer reference to the case, and creates the durable job. The case manager first
turns the complaint into typed investigation objectives. It may use the customer's
category selection as a hint, but the hint is not trusted as a fact.

The investigator then operates in an observe-and-act loop. It selects one tool at a
time based on current evidence, receives a provenanced result, and decides whether
another lookup is required. The available tools are fixed and read-only. More
importantly, trusted customer scope is injected by the server. If model-authored
arguments conflict with that scope, the tool rejects them. The loop is capped at
eight calls, which bounds latency, token use, and autonomous behavior.

The policy component receives the case category, material event date, query, and
the gathered evidence. Retrieval filters by effective date and scope before hybrid
ranking. The component assesses the returned sections and may identify one specific
missing evidence type. Only policy can trigger a supplemental lookup, and it gets
one pass. After that, the workflow proceeds or escalates. There is no unconstrained
conversation among agents.

The manager combines the complaint, source records, and applicable policy into a
grounded resolution proposal. Before another model sees it, deterministic
pre-verification checks citations, policy applicability, action shape, target and
value binding, and whether action evidence comes from a reliable source.

If those checks pass, the verifier receives the actual complaint, source records,
policy, and exact proposal. Its job is adversarial: identify missing support,
contradictions, or an unsupported disposition. It cannot call tools, change the
proposal, or enter a debate with the manager.

Finally, deterministic disposition logic maps the verified state to auto-resolution,
human approval, or human investigation. A mutation becomes an immutable action
intent and pauses the graph. Approval resumes at deterministic execution, where the
system re-reads the target under lock, checks that the state is unchanged, verifies
authorization and refundable balance, and uses a stable idempotency key.

The important point is that each handoff has a typed artifact and a clear owner. I
can inspect whether a failure came from planning, tool selection, retrieval,
proposal generation, verification, or execution rather than treating the entire
workflow as one model response."

### Slide 7 - 2:30

"I describe this as multi-agent because several model-backed roles have distinct
responsibilities, but the number of agents is not the point. The point is separation
of authority and failure modes.

The manager owns synthesis but cannot execute. The investigator can gather facts but
cannot write data or interpret policy as final authority. The policy component
assesses rules but does not invent operational facts. The verifier critiques the
exact proposal but cannot repair it or gather evidence. The action executor is
deterministic and can execute only the frozen, approved command.

This structure gives me three benefits. First, tool access is narrow. Only the
investigation component needs operational tools, and those are read-only. Second,
the artifacts are inspectable. An operator can see the plan, evidence, policy,
proposal, and review rather than receiving only a final answer. Third, evaluation is
component-level. Retrieval recall, evidence completeness, verifier behavior, and
action correctness can be measured separately.

The tradeoff is real: multiple calls add latency, tokens, and orchestration
complexity. One successful smoke case took more than a minute and used substantial
context, so I do not claim this topology is optimal. A simpler single-agent baseline
is an important next experiment. I deferred it until the primary workflow and
graders were stable enough to make the comparison meaningful.

So my defense of the architecture is conditional: these boundaries are useful for
this safety-sensitive workflow, and I would keep or remove them based on measured
quality, latency, and cost rather than the appeal of a multi-agent label."

### Slide 8 - 3:30

"The safety model starts with one rule: model output is a proposal, never authority.
There are controls at multiple layers because no single guardrail is sufficient.

At the access layer, the complaint and category are untrusted data. The server owns
customer scope, the tool catalog is fixed, and investigation tools are read-only.
This limits what prompt injection or an incorrect tool argument can access.

At probabilistic boundaries, Pydantic schemas validate plans, evidence summaries,
policy assessments, proposals, and verifier output. A valid schema does not prove
semantic correctness, but it prevents ambiguous or malformed objects from silently
flowing into later stages.

At the grounding layer, deterministic checks require real evidence and policy
citations. For an action, the target, amount, and supporting values must bind to a
reliable source record. The verifier then performs semantic critique using the
actual records, not only a summary written by the manager.

At the authority layer, deterministic disposition decides the next state. Model
confidence is deliberately absent. All MVP mutations require an authenticated human
approval, even for small amounts. The approved command is immutable and has a
before-state snapshot and stable hash.

At execution time, the service reauthorizes customer ownership, rechecks limits and
refundable balance, locks and compares current state with the approved snapshot, and
deduplicates using an idempotency key. If state changed after approval, execution
does not attempt to reinterpret the decision; it fails closed into human
investigation. A successful retry returns the stored receipt rather than creating a
second mutation.

This design addresses specific threats: cross-customer access, hallucinated facts,
wrong policy versions, duplicate refunds, stale approval, worker crashes, and
provider failures. It does not solve everything. Real tenant isolation, IAM,
customer identity verification, and provider-side reconciliation remain production
work. But the prototype makes the safety boundary explicit and testable."

### Slide 9 - 5:00 narrated demo

"I will now show one case rather than walk through every dashboard page. I chose a
cancellation-fee dispute because it exercises operational evidence, historical
policy, verification, and potentially an approval.

First, I submit the case through the customer intake form. The customer reference
and category enter as claims, and the complaint is treated as untrusted text. The
API returns a public case reference immediately; processing happens asynchronously
through the durable worker.

In the operations queue, the case moves from intake into processing. Opening the
workspace shows the case timeline and the artifacts created by each stage. Here is
the investigation plan. Notice that it contains explicit objectives rather than a
free-form internal monologue.

Next are the operational source records. I want to call out the provenance: these
are exact database-backed records associated with the trusted customer scope. The
investigator is not merely repeating facts from the complaint. It has checked the
appointment, cancellation, payment, and related account state.

Here is the policy evidence. The relevant section was filtered using the material
event date and business scope before semantic ranking. That matters because a newer
or similar-looking policy might produce a plausible but historically incorrect
decision.

The manager's proposal connects the source evidence to the policy. Beside it, the
verifier output shows whether the decision is supported and whether any material
gap or contradiction remains. This is a separate artifact rather than hidden
self-critique.

If this case requires only an explanation, the system can resolve it without a
write. If it proposes a refund, the workspace shows one frozen action: an exact
action type, target, amount, reason, and before-state. The model cannot change this
after approval.

I approve the action as the operations user. That decision is stored durably; the
web request does not execute the refund. The worker resumes the interrupted graph,
re-reads the payment under a lock, verifies that the approved before-state is still
current, and executes through an idempotent service. The resulting receipt and case
events appear in the audit trail.

If I retried the execution, it would return the existing receipt. If the payment had
changed between proposal and approval, the action would fail closed to human
investigation. Those lifecycle behaviors are covered by integration tests, so the
demo is illustrating the same path that the test suite exercises."

**Demo discipline:** Rehearse with a seeded case and keep screenshots available as
a fallback. Do not wait silently for a live model. If processing is slow, switch to
an already-completed case and continue narrating the artifacts.

### Slide 10 - 2:30

"Evaluation was designed alongside the workflow. The dataset contains 60 versioned
cases tied to the frozen business-data fingerprint. It has a development split for
iteration and an untouched held-out split for the final quality decision.

The graders focus on behavior: classification, final decision, disposition,
evidence completeness, source recall, policy recall, tool use, and exact action
type, target, and amount. Unauthorized and duplicate actions are explicit safety
metrics. Mutation cases stop at pending approval during live evaluation, so the
evaluator can grade the immutable action without changing shared evidence for later
cases. Execution safety is covered separately by integration tests.

I also added fault injection that makes one named tool unavailable through the real
workflow boundary. This tests whether the system escalates appropriately instead of
inventing missing evidence. Reports continue after individual case failures and
record the dataset, business fingerprint, model, provider, prompt version, tool
version, graph version, latency, tokens, and configured cost.

The held-out gates were frozen in advance: zero unauthorized actions, zero duplicate
executions, at least 95 percent unsafe-case escalation recall, at least 90 percent
decision accuracy, at least 95 percent disposition and evidence completeness, and
at least 90 percent policy recall. Latency and token cost are reported but cannot
compensate for a failed safety threshold.

I deliberately did not use an LLM judge to authorize actions. A future judge could
score tone or usefulness, but exact correctness and safety remain deterministic."

### Slide 11 - 2:00

"The evidence is mixed in a useful way. On the engineering side, PostgreSQL policy
retrieval achieved 16 out of 17 at recall@5, or 94.12 percent, above the frozen
90-percent gate. The latest full PostgreSQL-backed test snapshot contains 67 passing
tests. Formatting, lint, strict typing, the Next.js checks, the production build,
and CI also pass.

On live model quality, the evidence is intentionally more modest. One development
smoke case completed end to end and passed every applicable deterministic grader.
It also demonstrated retry recovery. But it is a sample of one, used an older prompt
and graph configuration, and took about 65 seconds with substantial token usage.
Several other attempts exposed provider and structured-output failures.

Therefore Gate E is still open. I do not have a full development result followed by
an untouched held-out result for the current frozen configuration. The correct
claim is that the complete path can work and the safety lifecycle is well tested,
not that the model has achieved a particular aggregate accuracy.

I include this slide because evaluation credibility depends on saying what the data
does not prove. In a real release process, I would tune only on development, freeze
the configuration, run held-out once, and block promotion if any safety threshold
failed."

### Slide 12 - 2:00

"The most valuable failures came from tracing the full workflow. Some were provider
availability issues such as 503s and timeouts. Others were structured-output errors.
One case gathered the correct evidence and policy but proposed an unsupported
action. The deterministic pre-verifier caught it and escalated, which is exactly the
desired fail-closed behavior.

The traces led to concrete boundary changes. Trusted customer scope was moved out
of model-authored tool arguments and injected by the server. Policy area and
effective date became deterministic inputs rather than model guesses. The action
proposal changed from an untyped dictionary into a constrained command schema. I
also added bounded stage-level retries for transient provider failures.

An important lesson was to classify failures correctly. A provider connection error
is not evidence that the model made a bad business decision. Conversely, a completed
but incorrect result is not excused as infrastructure noise. The evaluation reports
preserve these categories so I can improve the right layer.

I would also describe retrying carefully. More retries improve resilience to
transient failures, but unlimited retries increase cost and can duplicate work.
Here, retries are bounded, completed stages are durable, and execution is
idempotent. Observability did not merely make the system easier to debug; it changed
where I placed deterministic controls."

### Slide 13 - 1:30

"Several design decisions are worth making explicit. I allowed one supplemental
evidence pass instead of an agent debate because only new authoritative evidence can
resolve a material gap. PostgreSQL remains the business source of truth, while
checkpoints store only workflow position. Every MVP mutation requires approval
because I did not yet have risk-calibration evidence to justify an autonomous
monetary threshold.

I kept the verifier separate because generation and critique have different failure
modes, but the verifier is not a security boundary on its own. Deterministic checks
still own citations, authorization, disposition, and execution. I grade exact
actions deterministically rather than asking another model whether an amount looks
reasonable.

These choices are intentionally replaceable. With sufficient measurements, I might
merge components, allow low-risk autonomous actions, or use different infrastructure.
The principle is to change authority only when evidence supports the change."

### Slide 14 - 1:00

"The next priority is completing the live development evaluation, freezing the
configuration, and running the untouched held-out set. After quality validation, the
largest production gaps are real identity and tenant isolation, IAM and RBAC,
secrets management, backups, and deployment infrastructure.

The mock action executor would need real payment and booking integrations with
provider-side idempotency and reconciliation. Operationally, I would add lease
heartbeats, circuit breakers, provider fallback, and stronger event delivery. I
would then benchmark this architecture against a simpler baseline at representative
load.

So the project proves a production-minded workflow and its safety mechanics. It
does not claim production deployment readiness."

### Slide 15 - 0:30

"To close, Luma demonstrates how I design systems around probabilistic components:
bound tool authority, persist inspectable artifacts, make risky actions explicit,
and evaluate against frozen behavioral and safety gates.

The central lesson is that trustworthy agentic systems come from the deterministic
system around the model as much as from the model itself. I am happy to go deeper on
the architecture, the action lifecycle, or the evaluation design."

### Rehearsal checkpoints

- At 8:00, begin the system architecture slide.
- At 14:30, begin the component-boundary slide.
- At 20:30, begin the live demo.
- At 25:30, leave the demo even if a background run has not completed.
- At 30:00, begin the failure story.
- At 33:30, begin production gaps and closing.
- Stop at 35:00 and invite questions.

## Slides to cut or merge from the draft

- Remove the agenda slide unless the interview explicitly requires one.
- Replace the separate dashboard placeholder slides with one live demo slide.
- Merge the two AI architecture placeholders into the system architecture and
  component-boundary slides above.
- Merge "Trusting the AI," "Guardrails," and "Evals" into the safety and evaluation
  slides.
- Merge "My approach," "Challenges," and "Decisions" into the failure story and key
  decisions slides.
- Use one closing slide; remove the separate "Questions" and template "Thank you"
  slides.

This reduces the draft from 19 slides to 15, with only 12-13 content slides depending
on whether the demo and closing are counted.

## Presentation polish checklist

- Use sentence case for titles; avoid all caps.
- Keep each slide to one claim, at most 3-5 short bullets, and one visual.
- Replace placeholders such as "Dashboard pic" and "let's see" before presenting.
- Use "multi-agent system" or "multi-component agent workflow," not "MAS," until the
  term has been introduced.
- Use "case" consistently instead of alternating among ticket, request, and
  complaint.
- Say "human approval" for a proposed mutation and "human investigation" for an
  unresolved or unsafe case; they are different paths.
- Do not say the system is deterministic. Say deterministic controls constrain and
  validate probabilistic model behavior.
- Do not claim aggregate model accuracy until the full evaluation gate is complete.
- Remove leftover template metadata, including the incorrect date, names, and
  company on the final slide.

## Likely interview questions

- Why is the verifier separate from the proposal generator?
- Why PostgreSQL/pgvector instead of a document database plus a vector service?
- What stops cross-customer access or duplicate refunds?
- What happens if the worker crashes before or after approval?
- How does the system choose the correct historical policy?
- Why does the reasoning loop stop, and who may request more evidence?
- Which metrics block a release, and why is model confidence absent?
- At 100,000 cases per day, what would you replace first?

Answer with a concrete artifact, invariant, trace, metric, or test whenever possible.
