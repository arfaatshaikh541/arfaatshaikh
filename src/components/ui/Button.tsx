import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface BaseProps {
  variant?: "primary" | "secondary" | "ghost";
  children: ReactNode;
  className?: string;
}

const VARIANT_STYLES: Record<NonNullable<BaseProps["variant"]>, string> = {
  primary:
    "bg-orange text-black hover:bg-orange-bright border border-orange",
  secondary:
    "bg-transparent text-warm border border-line hover:border-orange hover:text-orange",
  ghost: "bg-transparent text-warm hover:text-orange",
};

const BASE_CLASSES =
  "inline-flex items-center justify-center gap-2 px-6 py-3 font-mono text-xs uppercase tracking-widest2 transition-colors duration-300 ease-cinematic focus-visible:outline-orange";

export function ButtonLink({
  href,
  variant = "primary",
  children,
  className,
}: BaseProps & { href: string }) {
  return (
    <Link href={href} className={cn(BASE_CLASSES, VARIANT_STYLES[variant], className)}>
      {children}
    </Link>
  );
}

export function Button({
  variant = "primary",
  children,
  className,
  ...props
}: BaseProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={cn(BASE_CLASSES, VARIANT_STYLES[variant], className)} {...props}>
      {children}
    </button>
  );
}
