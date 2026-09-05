import { serverApi } from "@/lib/server-api";
import type { PolicySearchResult } from "@/lib/types";

export default async function PoliciesPage({
  searchParams,
}: {
  searchParams: Promise<{ query?: string; effective_on?: string; policy_area?: string }>;
}) {
  const filters = await searchParams;
  const params = new URLSearchParams();
  if (filters.query) params.set("query", filters.query);
  if (filters.effective_on) params.set("effective_on", filters.effective_on);
  if (filters.policy_area) params.set("policy_area", filters.policy_area);
  const results = filters.query
    ? await serverApi<PolicySearchResult[]>(`operations/policies/search?${params}`)
    : [];

  return (
    <div className="page">
      <div className="page-heading"><div><p className="eyebrow">Knowledge</p>
        <h1>Policy search</h1><p>Find the policy version that applied when an event occurred.</p>
      </div></div>
      <section className="panel">
        <form className="policy-filters">
          <input name="query" defaultValue={filters.query} placeholder="Search cancellation, refund, booking…" required />
          <input name="effective_on" type="date" defaultValue={filters.effective_on} />
          <select name="policy_area" defaultValue={filters.policy_area ?? ""}>
            <option value="">All policy areas</option>
            <option value="cancellation">Cancellation</option>
            <option value="payments">Payments</option>
            <option value="membership">Membership</option>
            <option value="booking">Booking</option>
          </select>
          <button>Search policies</button>
        </form>
      </section>
      <section className="policy-results">
        {results.map((result) => (
          <article className="panel policy-result" key={result.section_id}>
            <div><span className="label">{result.policy_area}</span><strong>{result.section_id}</strong></div>
            <h2>{result.heading}</h2><p>{result.body}</p>
            <small>{result.policy_title} · version {result.version} · effective {result.effective_from}
              {result.effective_through ? ` through ${result.effective_through}` : " onward"}</small>
          </article>
        ))}
        {filters.query && !results.length && <div className="panel empty">No applicable policy sections found.</div>}
      </section>
    </div>
  );
}
