import Link from "next/link";
import { notFound } from "next/navigation";
import { serverApi } from "@/lib/server-api";
import type { PolicyDocument } from "@/lib/types";

export default async function PolicyDocumentPage({
  params,
  searchParams,
}: {
  params: Promise<{ sectionId: string }>;
  searchParams: Promise<{ case_reference?: string }>;
}) {
  const { sectionId } = await params;
  const { case_reference: caseReference } = await searchParams;
  const decodedSectionId = decodeURIComponent(sectionId);
  let policy: PolicyDocument;
  try {
    policy = await serverApi<PolicyDocument>(
      `operations/policies/sections/${encodeURIComponent(decodedSectionId)}`,
    );
  } catch {
    notFound();
  }

  const backHref = caseReference
    ? `/operations/cases/${encodeURIComponent(caseReference)}`
    : "/operations/policies";
  const backLabel = caseReference ? "Back to case" : "Back to policy search";

  return <div className="page policy-document-page">
    <Link className="policy-back-link" href={backHref}>← {backLabel}</Link>
    <div className="page-heading policy-document-heading"><div><p className="eyebrow">{policy.policy_area} policy</p>
      <h1>{policy.policy_title}</h1>
      <p>{policy.policy_id} · version {policy.version} · effective {policy.effective_from}{policy.effective_through ? ` through ${policy.effective_through}` : " onward"}</p>
    </div><span className="label">{policy.status}</span></div>
    <section className="panel policy-document">
      {policy.sections.map((section) => {
        const highlighted = section.section_id === policy.highlighted_section_id;
        return <article
          className={`policy-document-section${highlighted ? " highlighted" : ""}`}
          id={highlighted ? "relevant-policy-section" : undefined}
          key={section.section_id}
        >
          {highlighted && <span className="relevant-policy-label">Relevant section</span>}
          <small>{section.section_id}</small>
          <h2>{section.heading}</h2>
          <p>{section.body}</p>
        </article>;
      })}
    </section>
  </div>;
}
