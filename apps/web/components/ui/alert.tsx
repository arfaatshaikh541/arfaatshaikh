type Tone = "error" | "info" | "success" | "warning";

const toneClasses: Record<Tone, string> = {
  error: "border-red-800 bg-red-950/40 text-red-300",
  info: "border-surface-border bg-surface text-ink-muted",
  success: "border-emerald-800 bg-emerald-950/40 text-emerald-300",
  warning: "border-amber-800 bg-amber-950/40 text-amber-300",
};

export function Alert({ tone = "info", children }: { tone?: Tone; children: React.ReactNode }) {
  return <div className={`rounded-md border px-3.5 py-2.5 text-sm ${toneClasses[tone]}`}>{children}</div>;
}
