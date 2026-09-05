import Link from "next/link";
import { Label, Status } from "@/components/status";
import { serverApi } from "@/lib/server-api";
import type { ActionIntent } from "@/lib/types";

export default async function PendingPage() {
  const actions = await serverApi<ActionIntent[]>("actions/pending");
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">Human safety boundary</p><h1>Pending approvals</h1><p>Every write remains frozen until an operator reviews it.</p></div></div><section className="card-grid">{actions.map((action) => <article className="action-card" key={action.public_reference}><div><Label value={action.action_type}/><Status value={action.status}/></div><h2>{action.target_reference}</h2><p>Proposed change to {action.target_type}. Review the evidence and policy basis before deciding.</p><Link className="case-link" href={`/operations/cases/${action.case_reference}`}>Review {action.case_reference} →</Link></article>)}{!actions.length && <div className="empty-state"><span>✓</span><h2>No decisions waiting</h2><p>The approval queue is clear.</p></div>}</section></div>;
}
