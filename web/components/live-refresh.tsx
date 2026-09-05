"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function LiveRefresh() {
  const router = useRouter();
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    const events = new EventSource("/api/backend/operations/events");
    events.onopen = () => setConnected(true);
    events.onerror = () => setConnected(false);
    events.addEventListener("cases_changed", () => router.refresh());
    return () => events.close();
  }, [router]);
  return <span className={`live ${connected ? "connected" : ""}`}>{connected ? "Live" : "Reconnecting"}</span>;
}
