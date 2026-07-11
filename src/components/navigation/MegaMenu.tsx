import Link from "next/link";
import type { NavChild } from "@/types";

export default function MegaMenu({ items, id }: { items: NavChild[]; id: string }) {
  return (
    <div
      id={id}
      role="group"
      aria-label="Services menu"
      className="absolute left-1/2 top-full z-50 w-[720px] -translate-x-1/2 border border-line bg-black-graphite/98 p-2 shadow-[0_30px_60px_rgba(0,0,0,0.6)] backdrop-blur-sm"
    >
      <div className="grid grid-cols-2 gap-1 p-2">
        {items.map((child) => (
          <Link
            key={child.href}
            href={child.href}
            className="group flex flex-col gap-1 border border-transparent p-4 transition-colors hover:border-line hover:bg-black-surface"
          >
            <span className="font-display text-sm uppercase tracking-wide text-warmwhite group-hover:text-orange-bright">
              {child.label}
            </span>
            <span className="text-xs text-muted">{child.description}</span>
          </Link>
        ))}
      </div>
      <div className="gk-divider" />
      <div className="flex items-center justify-between p-4">
        <span className="gk-eyebrow">Full capability index</span>
        <Link href="/services" className="font-mono text-xs uppercase tracking-[0.14em] text-orange-primary hover:text-orange-bright">
          View all services →
        </Link>
      </div>
    </div>
  );
}
