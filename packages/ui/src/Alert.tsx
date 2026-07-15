import type { ReactNode } from "react";

type Tone = "info" | "success" | "error" | "warning";

const TONE_CLASS: Record<Tone, string> = {
  info: "border-severity-low/40 bg-severity-low/10 text-ink-900",
  success: "border-severity-resolved/40 bg-severity-resolved/10 text-ink-900",
  error: "border-severity-critical/40 bg-severity-critical/10 text-ink-900",
  warning: "border-severity-medium/40 bg-severity-medium/10 text-ink-900",
};

export function Alert({ tone = "info", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <div role={tone === "error" ? "alert" : "status"} className={["rounded border px-4 py-3 text-sm", TONE_CLASS[tone]].join(" ")}>
      {children}
    </div>
  );
}
