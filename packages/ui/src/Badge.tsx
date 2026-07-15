export type Severity = "critical" | "high" | "medium" | "low" | "info" | "resolved";

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Informational",
  resolved: "Resolved",
};

const SEVERITY_CLASS: Record<Severity, string> = {
  critical: "bg-severity-critical/15 text-severity-critical border-severity-critical/40",
  high: "bg-severity-high/15 text-severity-high border-severity-high/40",
  medium: "bg-severity-medium/15 text-severity-medium border-severity-medium/40",
  low: "bg-severity-low/15 text-severity-low border-severity-low/40",
  info: "bg-severity-info/15 text-severity-info border-severity-info/40",
  resolved: "bg-severity-resolved/15 text-severity-resolved border-severity-resolved/40",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-medium",
        SEVERITY_CLASS[severity],
      ].join(" ")}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  );
}

export function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: "neutral" | "positive" | "warning" }) {
  const toneClass =
    tone === "positive"
      ? "bg-severity-resolved/15 text-severity-resolved border-severity-resolved/40"
      : tone === "warning"
        ? "bg-severity-medium/15 text-severity-medium border-severity-medium/40"
        : "bg-surface-700 text-ink-500 border-surface-border";

  return (
    <span className={["inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-medium", toneClass].join(" ")}>
      {label}
    </span>
  );
}
