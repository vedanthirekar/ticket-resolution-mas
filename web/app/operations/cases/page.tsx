import { CaseTable } from "@/components/case-table";
import { serverApi } from "@/lib/server-api";
import type { CaseRecord } from "@/lib/types";

export default async function CasesPage({ searchParams }: { searchParams: Promise<{ status?: string; query?: string }> }) {
  const filters = await searchParams; const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status); if (filters.query) query.set("query", filters.query);
  const cases = await serverApi<CaseRecord[]>(`operations/cases?${query}`);
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">All work</p><h1>Case queue</h1><p>Review exceptions, approvals, and investigations.</p></div></div><section className="panel"><form className="filters"><input name="query" defaultValue={filters.query} placeholder="Search case, customer, or complaint"/><select name="status" defaultValue={filters.status ?? ""}><option value="">All statuses</option><option value="queued">Queued</option><option value="processing">Processing</option><option value="pending_approval">Pending approval</option><option value="human_investigation">Human investigation</option><option value="resolved">Resolved</option></select><button>Apply filters</button></form><CaseTable cases={cases}/></section></div>;
}
