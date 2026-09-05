"use client";

import { FormEvent, useState } from "react";

export default function LoginPage() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    const response = await fetch("/api/session/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: data.get("username"), password: data.get("password") }),
    });
    if (response.ok) window.location.assign("/operations");
    else { setError("Those credentials were not accepted."); setBusy(false); }
  }
  return <main className="auth-shell">
    <section className="auth-story"><div className="brand-mark">L</div><p className="eyebrow">Luma Wellness</p><h1>Every resolution needs a reason.</h1><p>Operational evidence, applicable policy, and a human safety boundary—together in one case workspace.</p></section>
    <section className="auth-panel"><form className="login-card" onSubmit={submit}><p className="eyebrow">Operations access</p><h2>Welcome back</h2><label>Username<input name="username" autoComplete="username" required autoFocus /></label><label>Password<input name="password" type="password" autoComplete="current-password" required /></label>{error && <p className="form-error">{error}</p>}<button className="primary-button" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button><a href="/submit" className="customer-link">Customer case intake →</a></form></section>
  </main>;
}
