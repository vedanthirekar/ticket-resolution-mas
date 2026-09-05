"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type Props = {
  caseReference: string;
  escalationStatus: string;
};

async function postUpdate(path: string, body?: Record<string, string>) {
  const response = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (response.ok) return;
  const payload = await response.json();
  throw new Error(typeof payload.detail === "string" ? payload.detail : "The update could not be saved.");
}

export function InvestigationControls({ caseReference, escalationStatus }: Props) {
  const router = useRouter();
  const [note, setNote] = useState("");
  const [resolutionCode, setResolutionCode] = useState("customer_guidance_provided");
  const [resolutionSummary, setResolutionSummary] = useState("");
  const [customerResponse, setCustomerResponse] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function update(kind: "acknowledge" | "note" | "resolve") {
    if (kind === "note" && !note.trim()) { setError("Add an investigation note first."); return; }
    if (kind === "resolve" && (!resolutionSummary.trim() || !customerResponse.trim())) {
      setError("Add both an internal resolution summary and a customer response."); return;
    }
    setBusy(kind); setError("");
    try {
      const base = `/api/backend/operations/cases/${caseReference}/investigation`;
      if (kind === "acknowledge") await postUpdate(`${base}/acknowledge`);
      if (kind === "note") {
        await postUpdate(`${base}/notes`, { note });
        setNote("");
      }
      if (kind === "resolve") {
        await postUpdate(`${base}/resolve`, {
          resolution_code: resolutionCode,
          resolution_summary: resolutionSummary,
          customer_response: customerResponse,
        });
      }
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The update could not be saved.");
    } finally {
      setBusy("");
    }
  }

  return <div className="investigation-controls">
    {escalationStatus === "open" && <button className="secondary-button" disabled={Boolean(busy)} onClick={() => update("acknowledge")}>{busy === "acknowledge" ? "Starting…" : "Start investigation"}</button>}
    <div className="investigation-form">
      <label>Investigation note<textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} maxLength={4000} placeholder="Record what you checked and what you found." /></label>
      <button className="secondary-button" disabled={Boolean(busy)} onClick={() => update("note")}>{busy === "note" ? "Saving…" : "Add note"}</button>
    </div>
    <details className="resolution-form">
      <summary>Complete human investigation</summary>
      <p>Closing records the manual decision. Any refund or credit adjustment must still use an approved action—do not use this form as a financial shortcut.</p>
      <label>Resolution type<select value={resolutionCode} onChange={(event) => setResolutionCode(event.target.value)}>
        <option value="customer_guidance_provided">Customer guidance provided</option>
        <option value="no_action_required">No account action required</option>
        <option value="corrected_externally">Correction completed in source system</option>
        <option value="other_manual_resolution">Other manual resolution</option>
      </select></label>
      <label>Internal resolution summary<textarea rows={3} value={resolutionSummary} onChange={(event) => setResolutionSummary(event.target.value)} maxLength={2000} placeholder="State the evidence checked and why this decision is appropriate." /></label>
      <label>Customer response<textarea rows={4} value={customerResponse} onChange={(event) => setCustomerResponse(event.target.value)} maxLength={4000} placeholder="Write the concise final answer the customer should receive." /></label>
      <button className="primary-button compact" disabled={Boolean(busy)} onClick={() => update("resolve")}>{busy === "resolve" ? "Completing…" : "Complete and close case"}</button>
    </details>
    {error && <p className="form-error">{error}</p>}
  </div>;
}
