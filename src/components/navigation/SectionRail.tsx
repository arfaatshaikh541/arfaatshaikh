"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { label: "Home", href: "/" },
  { label: "About", href: "/about" },
  { label: "Services", href: "/services" },
  { label: "Projects", href: "/projects" },
  { label: "Contact", href: "/contact" },
];

export function SectionRail() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <nav
      aria-label="Section"
      className="fixed inset-y-0 right-0 z-40 hidden flex-col items-end justify-center gap-5 py-28 pr-4 2xl:flex"
    >
      {SECTIONS.map((section, index) => {
        const active = isActive(section.href);
        return (
          <Link
            key={section.href}
            href={section.href}
            className={cn(
              "group flex flex-col items-end gap-0.5 text-right font-mono text-[10px] uppercase tracking-[0.1em] leading-tight transition-colors",
              active ? "text-[var(--color-blood-red)]" : "text-[var(--color-muted)] hover:text-[var(--color-off-white)]"
            )}
          >
            <span
              className={cn(
                "mb-1 h-px w-4 shrink-0 transition-all",
                active ? "bg-[var(--color-blood-red)]" : "bg-[var(--color-line)] group-hover:bg-[var(--color-muted)]"
              )}
            />
            <span>{String(index + 1).padStart(2, "0")}</span>
            <span>{section.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
