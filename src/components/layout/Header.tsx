"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_LINKS } from "@/lib/constants";
import { MegaMenu } from "@/components/navigation/MegaMenu";
import { MobileNav } from "@/components/navigation/MobileNav";
import { cn } from "@/lib/utils";

export function Header() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 24);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 border-b transition-colors duration-300",
        scrolled ? "border-line bg-black/85 backdrop-blur-md" : "border-transparent bg-transparent"
      )}
    >
      <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between px-6 md:px-10">
        <Link href="/" className="font-display text-lg tracking-widest2 text-warm">
          GRIDKEEP
        </Link>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Primary">
          {NAV_LINKS.filter((link) => link.label !== "Home").map((link) =>
            link.label === "Services" ? (
              <MegaMenu key={link.href} />
            ) : (
              <Link
                key={link.href}
                href={link.href}
                aria-current={pathname === link.href ? "page" : undefined}
                className={cn(
                  "font-mono text-xs uppercase tracking-widest2 transition-colors",
                  pathname === link.href ? "text-orange" : "text-warm hover:text-orange"
                )}
              >
                {link.label}
              </Link>
            )
          )}
        </nav>

        <div className="flex items-center gap-4">
          <Link
            href="/contact"
            className="hidden border border-orange px-5 py-2 font-mono text-xs uppercase tracking-widest2 text-orange transition-colors hover:bg-orange hover:text-black md:inline-flex"
          >
            Start a project
          </Link>
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="font-mono text-xs uppercase tracking-widest2 text-warm md:hidden"
            aria-label="Open navigation menu"
          >
            Menu
          </button>
        </div>
      </div>

      <MobileNav open={mobileOpen} onClose={() => setMobileOpen(false)} />
    </header>
  );
}
