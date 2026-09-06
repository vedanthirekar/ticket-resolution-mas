"use client";

import { FormEvent, useState } from "react";

const categories = [
  ["cancellation_fee_dispute", "Cancellation or no-show fee"],
  ["duplicate_payment", "Payment or duplicate charge"],
  ["missing_appointment", "Missing appointment"],
  ["membership_credits", "Membership credits"],
  ["online_booking_unavailable", "Online booking problem"],
  ["other", "Something else"],
];

export default function SubmitPage() {
  const [reference, setReference] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/backend/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        complaint_text: form.get("complaint"),
        claimed_customer_reference: form.get("customer") || null,
        contact_email: form.get("email"),
        claimed_category: form.get("category"),
        source: "manual",
        external_request_key: `manual-${crypto.randomUUID()}`,
      }),
    });
    const body = await response.json();
    if (response.ok) {
      setReference(body.public_reference);
    } else {
      setError(body.detail ?? "We could not submit your case.");
      setBusy(false);
    }
  }

  return (
    <main className="submit-shell">
      <div className="submit-brand">
        <span className="brand-mark small">L</span><span>Luma Wellness</span>
        <a href="/login">Operations sign in</a>
      </div>
      <section className="submit-card">
        {reference ? (
          <div className="success">
            <span>✓</span><p className="eyebrow">Case received</p>
            <h1>We’re looking into it.</h1>
            <p>Your reference is <strong>{reference}</strong>. Our resolution team now has your request and will prepare a final response for the email you provided.</p>
          </div>
        ) : (
          <>
            <p className="eyebrow">Customer care</p><h1>How can we help?</h1>
            <p>Tell us what happened. We’ll review your account activity and the policy that applies.</p>
            <form onSubmit={submit}>
              <label>Customer reference
                <input name="customer" placeholder="e.g. CUS-0001" required />
              </label>
              <label>Contact email
                <input name="email" type="email" autoComplete="email" placeholder="you@example.com" maxLength={320} required />
              </label>
              <label>What do you need help with?
                <select name="category" defaultValue="" required>
                  <option value="" disabled>Select an issue</option>
                  {categories.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                </select>
              </label>
              <label>What happened?
                <textarea name="complaint" rows={7} minLength={10} maxLength={10000} required
                  placeholder="Share useful dates, locations, or references if you have them." />
              </label>
              {error && <p className="form-error">{error}</p>}
              <button className="primary-button" disabled={busy}>{busy ? "Submitting…" : "Submit case"}</button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}
