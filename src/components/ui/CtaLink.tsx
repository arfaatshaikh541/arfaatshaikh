import Link from "next/link";
import { cn } from "@/lib/utils";

interface CtaLinkProps {
  href: string;
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  className?: string;
}

export function CtaLink({ href, children, variant = "primary", className }: CtaLinkProps) {
  return (
    <Link
      href={href}
      className={cn(
        "group inline-flex items-center gap-3 border px-6 py-3 font-mono text-xs uppercase tracking-[0.15em] transition-colors",
        variant === "primary"
          ? "border-[var(--color-blood-red)] bg-[var(--color-blood-red)] text-black hover:bg-transparent hover:text-[var(--color-blood-red)]"
          : "border-[var(--color-line)] text-[var(--color-off-white)] hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]",
        className
      )}
    >
      {children}
      <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
        →
      </span>
    </Link>
  );
}
