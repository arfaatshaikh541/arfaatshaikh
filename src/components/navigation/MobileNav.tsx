"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { navItems } from "@/data/nav";
import { LinkButton } from "@/components/ui/Button";

export default function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    panelRef.current?.querySelector("a")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <div
      className={`fixed inset-0 z-[100] transition-opacity duration-300 md:hidden ${
        open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
      }`}
      aria-hidden={!open}
    >
      <div className="absolute inset-0 bg-black/90" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Mobile navigation"
        className={`absolute right-0 top-0 flex h-full w-[86%] max-w-sm flex-col border-l border-line bg-black-graphite px-6 py-8 transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="mb-8 flex items-center justify-between">
          <span className="font-mono text-xs uppercase tracking-[0.24em] text-muted">Navigation</span>
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="flex h-9 w-9 items-center justify-center border border-line text-warmwhite hover:border-orange-bright hover:text-orange-bright"
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <div key={item.href} className="border-b border-white/5 py-3">
                <Link
                  href={item.href}
                  onClick={onClose}
                  className={`font-display text-xl uppercase tracking-wide ${
                    active ? "text-orange-bright" : "text-warmwhite"
                  }`}
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </Link>
                {item.children && (
                  <div className="mt-2 flex flex-col gap-2 pl-3">
                    {item.children.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        onClick={onClose}
                        className="font-mono text-xs uppercase tracking-[0.1em] text-muted hover:text-orange-primary"
                      >
                        {child.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
        <LinkButton href="/contact" className="mt-6 justify-center">
          Enter The System
        </LinkButton>
      </div>
    </div>
  );
}
