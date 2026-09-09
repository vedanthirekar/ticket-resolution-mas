import Link from "next/link";
import { notFound } from "next/navigation";
import { ApprovalControls } from "@/components/approval-controls";
import { CustomerEmail } from "@/components/customer-email";
import { InvestigationControls } from "@/components/investigation-controls";
import { RecordValue, recordLabel } from "@/components/record-value";
import { Label, Status } from "@/components/status";
import { serverApi } from "@/lib/server-api";
import type { CaseWorkspace } from "@/lib/types";

type AnyRecord = Record<string, unknown>;

function record(value: unknown): AnyRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as AnyRecord : {};
}

function evidenceData(evidence: CaseWorkspace["evidence"][number]): unknown {
  const outer = record(evidence.content);
  const content = record(outer.content);
  return content.data ?? outer.data ?? evidence.content;
}

function evidenceReferences(evidence: CaseWorkspace["evidence"][number]): string[] {
  const saved = record(evidence.content).source_references;
  if (Array.isArray(saved)) return saved.filter((item): item is string => typeof item === "string");
  return evidence.source_reference?.split(",").filter(Boolean) ?? [];
}

function evidenceSummary(evidence: CaseWorkspace["evidence"][number]): string {
  const data = evidenceData(evidence);
  const value = record(data);
  if (evidence.evidence_type === "customer_identity") {
    return `${value.display_name ?? "Customer"} · identity and contact status checked`;
  }
  if (evidence.evidence_type === "booking_history") {
    const count = Array.isArray(data) ? data.length : 0;
    return `${count} ${count === 1 ? "record" : "records"} reviewed`;
  }
  if (evidence.evidence_type === "appointment_timeline") {
    const appointment = record(value.appointment);
    const events = Array.isArray(value.events) ? value.events.length : 0;
    return `${appointment.appointment_reference ?? "Appointment"} · ${recordLabel(String(appointment.status ?? "status unknown"))} · ${events} timeline ${events === 1 ? "event" : "events"}`;
  }
  if (evidence.evidence_type === "payment") {
    const payments = Array.isArray(value.payments) ? value.payments.map(record) : [];
    const invoices = new Set(payments.map((payment) => payment.invoice_reference).filter(Boolean));
    const captured = payments.reduce((total, payment) => total + (typeof payment.captured_amount_cents === "number" ? payment.captured_amount_cents : 0), 0);
    return `${payments.length} ${payments.length === 1 ? "payment" : "payments"} across ${invoices.size} ${invoices.size === 1 ? "invoice" : "invoices"} · ${(captured / 100).toLocaleString("en-US", { style: "currency", currency: "USD" })} captured`;
  }
  if (evidence.evidence_type === "membership_ledger") {
    const ledger = Array.isArray(value.ledger) ? value.ledger.length : 0;
    return `${value.membership_reference ?? "Membership"} · ${value.derived_balance ?? "—"} credit balance · ${ledger} ledger ${ledger === 1 ? "entry" : "entries"}`;
  }
  if (evidence.evidence_type === "booking_configuration") {
    const facts = Array.isArray(value.configuration_facts) ? value.configuration_facts.length : 0;
    return `${value.booking_attempt_reference ?? "Booking attempt"} · ${recordLabel(String(value.status ?? "status unknown"))} · ${facts} configuration checks`;
  }
  return `${evidenceReferences(evidence).length} source records reviewed`;
}

function eventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    case_received: "Case received",
    case_queued: "Added to review queue",
    processing_started: "Investigation started",
    action_approval_requested: "Approval requested",
    case_escalated: "Sent for human investigation",
    case_resolved: "Case resolved",
    action_approved: "Action approved",
    action_rejected: "Action rejected",
    action_executed: "Action completed",
    human_investigation_started: "Human investigation started",
    human_investigation_note_added: "Investigation note added",
    human_investigation_resolved: "Human investigation completed",
    customer_email_draft_prepared: "Customer email draft prepared",
    customer_email_draft_updated: "Customer email draft updated",
    customer_email_mock_sent: "Customer email mock sent",
  };
  return labels[eventType] ?? recordLabel(eventType);
}

export default async function CasePage({ params }: { params: Promise<{ reference: string }> }) {
  const { reference } = await params;
  let item: CaseWorkspace;
  try { item = await serverApi<CaseWorkspace>(`operations/cases/${reference}`); } catch { notFound(); }
  const pending = item.actions.find((action) => action.status === "pending_approval");
  const researchUrl = item.claimed_customer_reference
    ? `/operations/records?customer_reference=${encodeURIComponent(item.claimed_customer_reference)}`
    : null;
  const citedEvidence = new Set(item.proposal?.evidence_references ?? []);
  const selectedPolicies = new Map<string, AnyRecord>();
  for (const retrieval of item.policy_retrievals) {
    for (const sectionId of retrieval.selected_section_ids) {
      const detail = retrieval.ranked_results.find((result) => result.section_id === sectionId);
      selectedPolicies.set(sectionId, detail ?? { section_id: sectionId, effective_from: retrieval.effective_on });
    }
  }
  const decisionState = item.verification
    ? item.verification.supported ? "Verified" : "Needs human review"
    : "Awaiting verification";
  const latestEscalation = item.escalations.at(-1);
  const investigationNotes = item.events.filter((event) => event.event_type === "human_investigation_note_added");
  const humanResolution = item.events.findLast((event) => event.event_type === "human_investigation_resolved");

  return <div className="page case-page">
    <div className="case-title">
      <div><p className="eyebrow">{item.public_reference}</p><h1>{item.plan?.category ? recordLabel(String(item.plan.category)) : "Unclassified case"}</h1><p>{item.claimed_customer_reference ?? "Customer identity not established"} · {item.contact_email ?? "No contact email"} · {new Date(item.received_at).toLocaleString()}</p></div>
      <div className="case-actions"><Status value={item.status}/>{researchUrl && <Link className="secondary-button" href={researchUrl}>Research customer records</Link>}</div>
    </div>
    <section className="complaint"><p className="eyebrow">Customer complaint</p><blockquote>“{item.complaint_text}”</blockquote></section>
    <div className="workspace-grid"><div className="workspace-main">
      {item.recommendation ? <section className={`panel decision-summary ${item.verification?.supported ? "verified" : item.verification ? "unverified" : ""}`}><div className="section-heading"><div><p className="eyebrow">Recommendation</p><h2>{item.recommendation.headline}</h2></div><span className={`decision-state ${item.verification?.supported ? "supported" : "attention"}`}>{decisionState}</span></div><p>{item.recommendation.explanation}</p>{item.recommendation.key_facts.length > 0 && <ul className="decision-facts">{item.recommendation.key_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>}<div className="decision-next"><strong>Next step</strong><span>{item.recommendation.next_step}</span></div><details className="decision-details"><summary>View decision details</summary><p>{item.recommendation.technical_rationale}</p>{item.proposal && <div className="decision-references"><span>Evidence: {item.proposal.evidence_references.join(", ") || "None"}</span><span>Policy: {item.proposal.policy_references.join(", ") || "None"}</span></div>}</details>{item.verification && !item.verification.supported && (item.verification.missing_evidence.length > 0 || item.verification.contradictions.length > 0) && <div className="issue-chips">{item.verification.missing_evidence.map((issue) => <span key={issue}>Missing: {recordLabel(issue)}</span>)}{item.verification.contradictions.map((issue) => <span key={issue}>Conflict: {recordLabel(issue)}</span>)}</div>}</section> : <section className="panel decision-summary"><p className="eyebrow">Recommendation</p><h2>Investigation in progress</h2><p>A recommendation will appear after the evidence and policy checks are complete.</p></section>}

      {item.escalations.length > 0 && researchUrl && <section className="research-callout"><div><p className="eyebrow">Human follow-up</p><h2>Need more information?</h2><p>Search the customer’s other appointments, invoices, payments, membership, and booking records.</p></div><Link className="primary-button compact" href={researchUrl}>Open business records →</Link></section>}

      {item.status === "human_investigation" && latestEscalation && <section className="panel investigation-panel"><div className="section-heading"><div><p className="eyebrow">Human investigation</p><h2>{recordLabel(latestEscalation.reason_code)}</h2></div><Status value={latestEscalation.status}/></div><p>Automation stopped safely. Review the records and policies, document what you find, then record a final response.</p>{investigationNotes.length > 0 && <div className="investigation-notes"><strong>Investigation history</strong>{investigationNotes.map((event) => <article key={event.sequence}><p>{String(event.payload.note ?? "")}</p><small>{recordLabel(event.actor_reference)} · {new Date(event.occurred_at).toLocaleString()}</small></article>)}</div>}<InvestigationControls caseReference={item.public_reference} escalationStatus={latestEscalation.status}/></section>}

      {humanResolution && <section className="panel human-resolution"><p className="eyebrow">Human resolution</p><h2>{recordLabel(String(humanResolution.payload.resolution_code ?? "Manual resolution"))}</h2><p>{String(humanResolution.payload.resolution_summary ?? "")}</p><div><strong>Customer response</strong><blockquote>{String(humanResolution.payload.customer_response ?? "")}</blockquote></div><small>Completed by {recordLabel(humanResolution.actor_reference)} · {new Date(humanResolution.occurred_at).toLocaleString()}</small></section>}

      <section className="panel detail evidence-section"><div className="section-heading"><div><p className="eyebrow">Supporting records</p><h2>Evidence reviewed</h2></div><span className="section-count">{item.evidence.length}</span></div>{item.evidence.map((evidence, index) => {
        const references = evidenceReferences(evidence);
        const supportsDecision = references.some((reference) => citedEvidence.has(reference));
        const conditionOk = evidence.condition === "present" || evidence.condition === "known_absent";
        return <details className="evidence-card" key={`${evidence.evidence_type}-${index}`}><summary><span className={`condition ${conditionOk ? "condition-good" : "condition-warning"}`}>{conditionOk ? "✓" : "!"}</span><div><strong>{recordLabel(evidence.evidence_type)}</strong><small>{evidenceSummary(evidence)}</small></div><span className={`evidence-use ${supportsDecision ? "used" : "reviewed"}`}>{supportsDecision ? "Used in decision" : "Reviewed"}</span><span className="expand-label">View details</span></summary><div className="evidence-details"><RecordValue name={evidence.evidence_type} value={evidenceData(evidence)}/><p className="evidence-source">Source: {references.join(", ") || "No matching record found"}</p></div></details>;
      })}{!item.evidence.length && <p className="muted">No operational records have been reviewed yet.</p>}</section>

      <section className="panel detail policy-section"><div className="section-heading"><div><p className="eyebrow">Knowledge</p><h2>Policies applied</h2></div><span className="section-count">{selectedPolicies.size}</span></div>{[...selectedPolicies].map(([sectionId, policy]) => <details className="policy-card" key={sectionId}><summary><div><strong>{String(policy.heading ?? sectionId)}</strong><small>{String(policy.policy_title ?? sectionId)} · {sectionId}</small></div><span>Read policy</span></summary><div className="policy-copy"><p>{String(policy.body || "Policy text is unavailable for this section.")}</p><small>Effective {String(policy.effective_from ?? "for the case event")}{policy.effective_through ? ` through ${String(policy.effective_through)}` : " onward"}</small><Link className="secondary-button policy-document-link" href={`/operations/policies/sections/${encodeURIComponent(sectionId)}?case_reference=${encodeURIComponent(item.public_reference)}#relevant-policy-section`}>View full policy →</Link></div></details>)}{!selectedPolicies.size && <p className="muted">No policy has been applied yet.</p>}</section>

      {pending && <section className="panel approval"><p className="eyebrow">Your decision</p><h2>Approve {recordLabel(pending.action_type)}?</h2><p>This action applies to <strong>{pending.target_reference}</strong>. Review the evidence and policy above before deciding.</p><details className="action-details"><summary>View exact proposed change</summary><RecordValue name="proposed change" value={pending.action_payload.command}/></details><ApprovalControls actionReference={pending.public_reference}/></section>}

      {item.final_communication && <CustomerEmail caseReference={item.public_reference} initial={item.final_communication} />}
      {item.status === "resolved" && !item.final_communication && <section className="panel customer-email unavailable"><p className="eyebrow">Customer notification</p><h2>No email draft available</h2><p>{item.contact_email ? "This older case was resolved before final email drafting was enabled." : "No contact email was supplied when this case was submitted."}</p></section>}
    </div><aside className="timeline panel"><p className="eyebrow">Case history</p><h2>What happened</h2>{item.events.map((event) => <div className="timeline-event" key={event.sequence}><span></span><div><strong>{eventLabel(event.event_type)}</strong><small>{new Date(event.occurred_at).toLocaleTimeString()} · {recordLabel(event.actor_type)}</small></div></div>)}</aside></div>
  </div>;
}
