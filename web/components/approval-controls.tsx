"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function ApprovalControls({ actionReference }: { actionReference: string }) {
  const router = useRouter();
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function decide(decision: "approved" | "rejected") {
    if (!rationale.trim()) { setError("Add a short decision rationale."); return; }
    setBusy(true); setError("");
    const response = await fetch(`/api/backend/actions/${actionReference}/decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, rationale }) });
    if (response.ok) router.refresh(); else { const payload = await response.json(); setError(payload.detail ?? "Decision could not be recorded."); setBusy(false); }
  }
  return <div className="approval-box"><label>Decision note<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="What did you verify?" rows={3}/></label>{error && <p className="form-error">{error}</p>}<div className="button-row"><button className="primary-button compact" disabled={busy} onClick={() => decide("approved")}>Approve action</button><button className="danger-button" disabled={busy} onClick={() => decide("rejected")}>Reject &amp; escalate</button></div></div>;
}
