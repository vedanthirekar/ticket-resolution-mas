import type { ReactNode } from "react";

export function recordLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function scalar(key: string, value: string | number | boolean | null): ReactNode {
  if (value === null) return <span className="record-empty">Not recorded</span>;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" && key.endsWith("_cents")) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value / 100);
  }
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return new Date(value).toLocaleString();
  }
  return String(value);
}

export function RecordValue({ name, value, depth = 0 }: { name: string; value: unknown; depth?: number }) {
  if (Array.isArray(value)) {
    if (!value.length) return <div className="record-section"><h3>{recordLabel(name)}</h3><p className="muted">No records found.</p></div>;
    return <div className="record-section"><h3>{recordLabel(name)} <small>{value.length}</small></h3><div className="record-list">{value.map((item, index) => <article className="record-card" key={index}><RecordValue name={`${recordLabel(name)} ${index + 1}`} value={item} depth={depth + 1}/></article>)}</div></div>;
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    const simple = entries.filter(([, item]) => item === null || ["string", "number", "boolean"].includes(typeof item));
    const nested = entries.filter(([, item]) => !(item === null || ["string", "number", "boolean"].includes(typeof item)));
    return <div className={depth ? "record-group" : "record-root"}>{depth > 1 && <h4>{recordLabel(name)}</h4>}<dl>{simple.map(([key, item]) => <div key={key}><dt>{recordLabel(key.replace(/_cents$/, ""))}</dt><dd>{scalar(key, item as string | number | boolean | null)}</dd></div>)}</dl>{nested.map(([key, item]) => key === "provenance" ? <details className="provenance" key={key}><summary>Source details</summary><RecordValue name={key} value={item} depth={depth + 1}/></details> : <RecordValue key={key} name={key} value={item} depth={depth + 1}/>)}</div>;
  }
  return <div><strong>{recordLabel(name)}</strong>: {scalar(name, value as string | number | boolean | null)}</div>;
}
