import type { HTMLAttributes, ReactNode } from "react";

export function Card({ children, className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={[
        "rounded-md border border-surface-border bg-surface-900 p-5 shadow-sm",
        className,
      ].join(" ")}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <div className="mb-4">
      <h2 className="text-base font-semibold text-ink-900">{title}</h2>
      {description ? <p className="mt-1 text-sm text-ink-500">{description}</p> : null}
    </div>
  );
}
