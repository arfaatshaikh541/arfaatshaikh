import type { ReactNode } from "react";

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "success" | "danger" }) {
  return <div className={`notice notice-${tone}`} role={tone === "danger" ? "alert" : "status"}>{children}</div>;
}
