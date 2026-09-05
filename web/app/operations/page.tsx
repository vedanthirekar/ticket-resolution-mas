import Link from "next/link";
import { CaseTable } from "@/components/case-table";
import { serverApi } from "@/lib/server-api";
import type { CaseRecord, Overview } from "@/lib/types";

export default async function OverviewPage() {
  const [overview, cases] = await Promise.all([serverApi<Overview>("operations/overview"), serverApi<CaseRecord[]>("operations/cases?limit=8")]);
  const formatDuration = overview.average_resolution_seconds == null ? "—" : `${overview.average_resolution_seconds.toFixed(1)}s`;
  return <div className="page"><div className="page-heading"><div><h1>Good morning.</h1><p>Here’s how the resolution queue is moving.</p></div><Link className="primary-button compact" href="/operations/cases">View all cases</Link></div><section className="metrics"><article><span>Active cases</span><strong>{overview.active_cases}</strong><small>Queued or processing</small></article><article><span>Pending approval</span><strong>{overview.pending_approval_cases}</strong><small>Waiting for your decision</small></article><article><span>Human investigation</span><strong>{overview.human_investigation_cases}</strong><small>Evidence or policy gaps</small></article><article><span>Resolution rate</span><strong>{overview.resolution_rate == null ? "—" : `${(overview.resolution_rate * 100).toFixed(0)}%`}</strong><small>Avg. resolution {formatDuration}</small></article></section><section className="panel"><div className="panel-heading"><div><p className="eyebrow">Latest activity</p><h2>Case queue</h2></div></div><CaseTable cases={cases} /></section></div>;
}
