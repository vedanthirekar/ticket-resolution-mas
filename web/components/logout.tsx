"use client";

export function Logout() {
  async function logout() {
    await fetch("/api/session/logout", { method: "POST" });
    window.location.assign("/login");
  }
  return <button className="text-button" onClick={logout}>Sign out</button>;
}
