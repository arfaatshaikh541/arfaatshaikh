import Link from "next/link";
import type { ButtonHTMLAttributes } from "react";

interface BaseProps {
  variant?: "primary" | "secondary";
  children: React.ReactNode;
  className?: string;
}

interface LinkButtonProps extends BaseProps {
  href: string;
}

const base =
  "inline-flex items-center gap-2.5 px-6 py-3.5 font-mono text-xs uppercase tracking-[0.18em] transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-bright";

const variants = {
  primary: "bg-orange-primary text-black hover:bg-orange-bright",
  secondary: "border border-line text-warmwhite hover:border-orange-bright hover:text-orange-bright",
};

export function LinkButton({ href, variant = "primary", children, className = "" }: LinkButtonProps) {
  return (
    <Link href={href} className={`${base} ${variants[variant]} ${className}`}>
      {children}
    </Link>
  );
}

export function Button({
  variant = "primary",
  children,
  className = "",
  ...rest
}: BaseProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}
