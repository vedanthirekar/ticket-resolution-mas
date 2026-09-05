import Link from "next/link";
import { redirect } from "next/navigation";
import { LiveRefresh } from "@/components/live-refresh";
import { Logout } from "@/components/logout";
import { serverApi } from "@/lib/server-api";

export default async function OperationsLayout({ children }: { children: React.ReactNode }) {
  let account: { display_name: string };
  try { account = await serverApi("auth/me"); } catch { redirect("/login"); }
  return <div className="app-shell"><aside className="sidebar"><div><div className="brand"><span className="brand-mark small">L</span><span>Luma<strong>Resolution Center</strong></span></div><nav><Link href="/operations">Overview</Link><Link href="/operations/cases">Case queue</Link><Link href="/operations/pending">Approvals</Link><Link href="/operations/records">Business records</Link><Link href="/operations/policies">Policy search</Link></nav></div><div className="account"><span className="avatar">{account.display_name.charAt(0)}</span><div><strong>{account.display_name}</strong><small>Operations</small></div><Logout /></div></aside><main className="main"><header className="topbar"><div><p className="eyebrow">Operations workspace</p><span>Evidence-grounded case resolution</span></div><LiveRefresh /></header>{children}</main></div>;
}
