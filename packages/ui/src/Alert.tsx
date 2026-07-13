import { HTMLAttributes } from "react";
import clsx from "clsx";

type Tone = "info" | "success" | "error";

const toneClasses: Record<Tone, string> = {
  info: "border-surface-700 bg-surface-800 text-surface-200",
  success: "border-emerald-800 bg-emerald-950 text-emerald-300",
  error: "border-red-800 bg-red-950 text-red-300",
};

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  tone?: Tone;
}

export function Alert({ tone = "info", className, ...props }: AlertProps) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={clsx("rounded-md border px-3.5 py-2.5 text-sm", toneClasses[tone], className)}
      {...props}
    />
  );
}
