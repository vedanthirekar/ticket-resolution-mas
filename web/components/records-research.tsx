"use client";

import { FormEvent, useEffect, useState } from "react";
import { RecordValue, recordLabel } from "@/components/record-value";
import type { OperationsResearchResult } from "@/lib/types";

type Lookup = "get_customer" | "get_customer_appointments" | "get_appointment_timeline" |
  "get_appointment_payments" | "get_membership_evidence" |
  "get_customer_booking_attempts" | "get_booking_attempt_evidence";

const lookupOptions: Array<{ value: Lookup; label: string; reference?: string }> = [
  { value: "get_customer", label: "Customer profile" },
  { value: "get_customer_appointments", label: "Appointment history" },
  { value: "get_appointment_timeline", label: "Appointment timeline", reference: "Appointment reference" },
  { value: "get_appointment_payments", label: "Invoices & payments", reference: "Appointment reference" },
  { value: "get_membership_evidence", label: "Membership & credit ledger", reference: "Membership reference (optional)" },
  { value: "get_customer_booking_attempts", label: "Booking attempts" },
  { value: "get_booking_attempt_evidence", label: "Booking configuration", reference: "Booking attempt reference" },
];

export function RecordsResearch({ initialCustomerReference, initialAppointmentReference }: { initialCustomerReference: string; initialAppointmentReference: string }) {
  const [lookup, setLookup] = useState<Lookup>(initialAppointmentReference ? "get_appointment_timeline" : "get_customer");
  const [customerReference, setCustomerReference] = useState(initialCustomerReference);
  const [relatedReference, setRelatedReference] = useState(initialAppointmentReference);
  const [asOf, setAsOf] = useState(() => new Date().toISOString().slice(0, 10));
  const [result, setResult] = useState<OperationsResearchResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const option = lookupOptions.find((item) => item.value === lookup)!;

  async function runResearch(selectedLookup = lookup) {
    if (!customerReference.trim()) { setError("Enter a customer reference."); return; }
    const selected = lookupOptions.find((item) => item.value === selectedLookup)!;
    if (selected.reference && !selected.reference.includes("optional") && !relatedReference.trim()) { setError(`Enter the ${selected.reference.toLowerCase()}.`); return; }
    const arguments_: Record<string, unknown> = { customer_reference: customerReference.trim() };
    if (selectedLookup === "get_appointment_timeline" || selectedLookup === "get_appointment_payments") arguments_.appointment_reference = relatedReference.trim();
    if (selectedLookup === "get_membership_evidence") { if (relatedReference.trim()) arguments_.membership_reference = relatedReference.trim(); arguments_.as_of = `${asOf}T23:59:59Z`; arguments_.limit = 200; }
    if (selectedLookup === "get_booking_attempt_evidence") arguments_.booking_attempt_reference = relatedReference.trim();
    if (selectedLookup === "get_customer_appointments" || selectedLookup === "get_customer_booking_attempts") arguments_.limit = 50;
    setBusy(true); setError(""); setResult(null);
    const response = await fetch("/api/backend/operations/research", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tool_name: selectedLookup, arguments: arguments_ }) });
    const payload = await response.json();
    if (response.ok) setResult(payload); else setError(typeof payload.detail === "string" ? payload.detail : "The records could not be retrieved.");
    setBusy(false);
  }

  useEffect(() => { if (initialCustomerReference) void runResearch(lookup); }, []); // Open case links directly into useful records.

  function submit(event: FormEvent) { event.preventDefault(); void runResearch(); }
  function choose(next: Lookup) { setLookup(next); setRelatedReference(""); setResult(null); setError(""); }

  return <div className="records-workspace"><section className="panel research-panel"><form onSubmit={submit}><label>Customer reference<input value={customerReference} onChange={(event) => setCustomerReference(event.target.value)} placeholder="CUS-0001" required /></label><label>Record set<select value={lookup} onChange={(event) => choose(event.target.value as Lookup)}>{lookupOptions.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label>{option.reference && <label>{option.reference}<input value={relatedReference} onChange={(event) => setRelatedReference(event.target.value)} placeholder={option.reference.startsWith("Appointment") ? "APPT-..." : option.reference.startsWith("Membership") ? "MEM-..." : "BATT-..."} required={!option.reference.includes("optional")} /></label>}{lookup === "get_membership_evidence" && <label>Ledger as of<input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} required /></label>}<button disabled={busy}>{busy ? "Retrieving…" : "View records"}</button></form><p>All lookups are read-only and customer-scoped. Related records must belong to the customer entered above.</p></section>{error && <div className="panel research-error"><strong>Records not found</strong><p>{error}</p></div>}{result && <section className="research-results"><div className="result-heading"><div><p className="eyebrow">{recordLabel(result.evidence_type)}</p><h2>{option.label}</h2></div><div><strong>{result.metadata.result_count}</strong><span>source records</span></div></div><div className="source-banner"><span>Authoritative source: Luma PostgreSQL</span><span>Retrieved {new Date(result.metadata.executed_at).toLocaleString()}</span>{result.metadata.truncated && <span>Result limit reached</span>}</div><div className="panel record-output"><RecordValue name="result" value={result.data}/></div></section>}</div>;
}
