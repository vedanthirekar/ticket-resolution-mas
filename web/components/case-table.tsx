import Link from "next/link";
import type { CaseRecord } from "@/lib/types";
import { Label, Status } from "./status";

const age = (received: string) => {
  const seconds = Math.max(0, (Date.now() - new Date(received).getTime()) / 1000);
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h`;
};

export function CaseTable({ cases }: { cases: CaseRecord[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Case</th><th>Category</th><th>Status</th><th>Priority</th><th>Source</th><th>Age</th></tr></thead>
        <tbody>
          {cases.map((item) => (
            <tr key={item.public_reference}>
              <td><Link className="case-link" href={`/operations/cases/${item.public_reference}`}>{item.public_reference}</Link><small>{item.complaint_text}</small></td>
              <td><Label value={item.category ?? item.claimed_category} /></td>
              <td><Status value={item.status} /></td>
              <td className={`priority priority-${item.priority}`}>{item.priority}</td>
              <td>{item.source}</td><td>{age(item.received_at)}</td>
            </tr>
          ))}
          {!cases.length && <tr><td colSpan={6} className="empty">No cases match this view.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
