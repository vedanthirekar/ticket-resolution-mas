"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { CaseWorkspace } from "@/lib/types";

type Communication = NonNullable<CaseWorkspace["final_communication"]>;

export function CustomerEmail({
  caseReference,
  initial,
}: {
  caseReference: string;
  initial: Communication;
}) {
  const router = useRouter();
  const [subject, setSubject] = useState(initial.subject);
  const [body, setBody] = useState(initial.body);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const sent = initial.status === "sent";

  async function submit(kind: "save" | "send") {
    setBusy(kind);
    setError("");
    try {
      const suffix = kind === "save" ? "draft" : "send";
      const response = await fetch(
        `/api/backend/operations/cases/${caseReference}/customer-communication/${suffix}`,
        {
          method: kind === "save" ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ subject, body }),
        },
      );
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(
          typeof payload.detail === "string" ? payload.detail : "The email update failed.",
        );
      }
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The email update failed.");
    } finally {
      setBusy("");
    }
  }

  return (
    <section className={`panel customer-email ${sent ? "email-sent" : ""}`}>
      <div className="section-heading">
        <div>
          <p className="eyebrow">Customer notification</p>
          <h2>{sent ? "Mock email sent" : "Final email draft"}</h2>
        </div>
        <span className={`decision-state ${sent ? "supported" : "attention"}`}>
          {sent ? "Sent" : "Review required"}
        </span>
      </div>
      <p className="email-recipient"><strong>To</strong> {initial.recipient_email}</p>
      <label>
        Subject
        <input
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          maxLength={240}
          readOnly={sent}
        />
      </label>
      <label>
        Message
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={11}
          maxLength={10000}
          readOnly={sent}
        />
      </label>
      {sent ? (
        <p className="delivery-detail">
          Sent by {initial.sent_by ?? "an employee"} on {initial.sent_at ? new Date(initial.sent_at).toLocaleString() : "—"}
          {initial.delivery_reference ? ` · ${initial.delivery_reference}` : ""}
        </p>
      ) : (
        <>
          <p className="mock-notice">Prototype mode: Send email records a mock delivery; no external email is sent.</p>
          <div className="button-row email-actions">
            <button className="secondary-button" disabled={Boolean(busy)} onClick={() => submit("save")}>
              {busy === "save" ? "Saving…" : "Save draft"}
            </button>
            <button className="primary-button compact" disabled={Boolean(busy)} onClick={() => submit("send")}>
              {busy === "send" ? "Sending…" : "Send Email"}
            </button>
          </div>
        </>
      )}
      {error && <p className="form-error">{error}</p>}
    </section>
  );
}
