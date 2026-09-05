export function Status({ value }: { value: string }) {
  return <span className={`status status-${value}`}>{value.replaceAll("_", " ")}</span>;
}

export function Label({ value }: { value: string | null | undefined }) {
  return <span className="label">{value ? value.replaceAll("_", " ") : "Unclassified"}</span>;
}
