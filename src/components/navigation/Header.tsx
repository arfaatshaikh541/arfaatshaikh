"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Logo from "@/components/ui/Logo";
import { LinkButton } from "@/components/ui/Button";
import MegaMenu from "./MegaMenu";
import MobileNav from "./MobileNav";
import ScrollProgress from "./ScrollProgress";
import { navItems } from "@/data/nav";

export default function Header() {
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(null);
  }, [pathname]);

  return (
    <>
      <header
        className={`fixed left-0 top-0 z-[90] w-full border-b transition-colors duration-300 ${
          scrolled ? "border-line bg-black/92 backdrop-blur-md" : "border-transparent bg-gradient-to-b from-black/70 to-transparent"
        }`}
        style={{ height: "var(--header-height)" }}
      >
        <div className="mx-auto flex h-full max-w-[1440px] items-center justify-between px-6 md:px-10">
          <Logo />

          <nav aria-label="Primary" className="hidden items-center gap-7 md:flex">
            {navItems.map((item) => {
              const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
              const hasMenu = !!item.children;
              return (
                <div
                  key={item.href}
                  className="relative"
                  onMouseEnter={() => hasMenu && setMenuOpen(item.label)}
                  onMouseLeave={() => hasMenu && setMenuOpen(null)}
                >
                  <Link
                    href={item.href}
                    aria-haspopup={hasMenu ? "true" : undefined}
                    aria-expanded={hasMenu ? menuOpen === item.label : undefined}
                    aria-current={active ? "page" : undefined}
                    onFocus={() => hasMenu && setMenuOpen(item.label)}
                    className={`relative flex items-center gap-1 py-2 font-mono text-[11px] uppercase tracking-[0.16em] transition-colors ${
                      active ? "text-orange-bright" : "text-warmwhite/85 hover:text-orange-bright"
                    }`}
                  >
                    {item.label}
                    {hasMenu && (
                      <span aria-hidden="true" className="text-[8px]">
                        ▾
                      </span>
                    )}
                    {active && (
                      <span className="absolute -bottom-[9px] left-0 h-[2px] w-full bg-orange-primary" aria-hidden="true" />
                    )}
                  </Link>
                  {hasMenu && menuOpen === item.label && <MegaMenu id="services-menu" items={item.children!} />}
                </div>
              );
            })}
          </nav>

          <div className="hidden md:block">
            <LinkButton href="/contact">Enter The System</LinkButton>
          </div>

          <button
            className="flex h-10 w-10 flex-col items-center justify-center gap-1.5 border border-line md:hidden"
            aria-label="Open menu"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(true)}
          >
            <span className="h-px w-5 bg-warmwhite" aria-hidden="true" />
            <span className="h-px w-5 bg-warmwhite" aria-hidden="true" />
          </button>
        </div>
      </header>
      <ScrollProgress />
      <MobileNav open={mobileOpen} onClose={() => setMobileOpen(false)} />
    </>
  );
}
