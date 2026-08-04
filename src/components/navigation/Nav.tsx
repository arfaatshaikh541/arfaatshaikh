"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { services } from "@/data/services";
import { cn } from "@/lib/utils";
import { ScrollProgress } from "./ScrollProgress";

const NAV_LINKS = [
  { label: "Home", href: "/" },
  { label: "About", href: "/about" },
  { label: "Services", href: "/services" },
  { label: "Projects", href: "/projects" },
  { label: "GRIDKEEP", href: "/gridkeep" },
  { label: "Insights", href: "/insights" },
  { label: "Tech Stack", href: "/tech-stack" },
  { label: "Process", href: "/process" },
  { label: "Contact", href: "/contact" },
];

function LogoMark() {
  return (
    <svg
      aria-hidden="true"
      width="30"
      height="30"
      viewBox="0 0 30 30"
      className="shrink-0"
    >
      <path d="M15 2 L27 26 L19 26 L15 17 L11 26 L3 26 Z" fill="var(--color-blood-red)" />
      <path d="M15 2 L27 26 L19 26 L15 17 Z" fill="var(--color-hot-red)" opacity="0.55" />
    </svg>
  );
}

export function Nav() {
  const pathname = usePathname();
  const [servicesOpen, setServicesOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const mobileToggleRef = useRef<HTMLButtonElement>(null);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    // Close any open menu on navigation. Intentional: this reacts to the
    // route (an external signal), not to state Nav itself owns.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMobileOpen(false);
    setServicesOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!servicesOpen) return;
    const onClick = (event: MouseEvent) => {
      if (!dropdownRef.current?.contains(event.target as Node)) {
        setServicesOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setServicesOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [servicesOpen]);

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    if (!mobileOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
        mobileToggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="fixed inset-x-0 top-0 z-[100]">
      <ScrollProgress />
      <div className="container-edge flex h-16 items-center justify-between border-b border-[var(--color-line)] bg-black/70 backdrop-blur-md md:h-20">
        <Link href="/" className="flex items-center gap-2.5">
          <LogoMark />
          <span className="flex flex-col leading-none">
            <span className="font-display text-lg uppercase tracking-wide text-[var(--color-off-white)] md:text-xl">
              Arfaat<span className="text-[var(--color-blood-red)]">.</span>
            </span>
            <span className="hidden font-mono text-[9px] uppercase tracking-[0.3em] text-[var(--color-muted)] sm:block">
              Shaikh
            </span>
          </span>
        </Link>

        <nav
          aria-label="Primary"
          className="hidden items-center gap-1 lg:flex"
        >
          {NAV_LINKS.map((link) =>
            link.label === "Services" ? (
              <div key={link.href} ref={dropdownRef} className="relative">
                <button
                  type="button"
                  aria-expanded={servicesOpen}
                  aria-controls="services-menu"
                  onClick={() => setServicesOpen((v) => !v)}
                  className={cn(
                    "flex items-center gap-1 rounded px-2.5 py-2 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--color-muted)] transition-colors hover:text-[var(--color-off-white)] xl:px-3 xl:text-xs xl:tracking-[0.12em]",
                    isActive(link.href) && "text-[var(--color-off-white)]"
                  )}
                >
                  Services
                  <svg
                    aria-hidden="true"
                    width="10"
                    height="10"
                    viewBox="0 0 10 10"
                    className={cn(
                      "transition-transform",
                      servicesOpen && "rotate-180"
                    )}
                  >
                    <path
                      d="M1 3l4 4 4-4"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      fill="none"
                    />
                  </svg>
                </button>
                {servicesOpen && (
                  <div
                    id="services-menu"
                    role="menu"
                    aria-label="Services"
                    className="absolute left-1/2 top-full w-72 -translate-x-1/2 border border-[var(--color-line)] bg-[var(--color-surface)] p-2 shadow-[0_20px_60px_rgba(0,0,0,0.6)]"
                  >
                    {services.map((service) => (
                      <Link
                        key={service.slug}
                        role="menuitem"
                        href={`/services/${service.slug}`}
                        className="block rounded px-4 py-3 transition-colors hover:bg-[var(--color-surface-raised)]"
                      >
                        <span className="block text-sm text-[var(--color-off-white)]">
                          {service.shortName}
                        </span>
                        <span className="mt-0.5 block font-mono text-[11px] text-[var(--color-muted)]">
                          {service.tagline}
                        </span>
                      </Link>
                    ))}
                    <Link
                      role="menuitem"
                      href="/services"
                      className="mt-1 block rounded px-4 py-3 font-mono text-xs uppercase tracking-[0.1em] text-[var(--color-blood-red)] transition-colors hover:bg-[var(--color-surface-raised)]"
                    >
                      All services →
                    </Link>
                  </div>
                )}
              </div>
            ) : (
              <Link
                key={link.href}
                href={link.href}
                aria-current={isActive(link.href) ? "page" : undefined}
                className={cn(
                  "relative rounded px-2.5 py-2 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--color-muted)] transition-colors hover:text-[var(--color-off-white)] xl:px-3 xl:text-xs xl:tracking-[0.12em]",
                  isActive(link.href) && "text-[var(--color-off-white)]"
                )}
              >
                {link.label}
                {isActive(link.href) && (
                  <span className="absolute -bottom-[1px] left-4 right-4 h-[2px] bg-[var(--color-blood-red)]" />
                )}
              </Link>
            )
          )}
        </nav>

        <button
          ref={mobileToggleRef}
          type="button"
          className="flex h-10 w-10 flex-col items-center justify-center gap-1.5 rounded-full border border-[var(--color-line)] transition-colors hover:border-[var(--color-blood-red)] lg:hidden"
          aria-expanded={mobileOpen}
          aria-controls="mobile-menu"
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          onClick={() => setMobileOpen((v) => !v)}
        >
          <span
            className={cn(
              "block h-[1.5px] w-6 bg-[var(--color-off-white)] transition-transform",
              mobileOpen && "translate-y-[3.5px] rotate-45"
            )}
          />
          <span
            className={cn(
              "block h-[1.5px] w-6 bg-[var(--color-off-white)] transition-transform",
              mobileOpen && "-translate-y-[3.5px] -rotate-45"
            )}
          />
        </button>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            id="mobile-menu"
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: prefersReducedMotion ? 0 : -12 }}
            transition={{ duration: prefersReducedMotion ? 0.01 : 0.2, ease: "easeOut" }}
            className="fixed inset-x-0 top-16 bottom-0 z-[90] overflow-y-auto bg-black lg:hidden"
          >
            <nav
              aria-label="Mobile"
              className="container-edge flex flex-col gap-1 py-8"
            >
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={isActive(link.href) ? "page" : undefined}
                  className="border-b border-[var(--color-line)] py-4 font-display text-3xl uppercase text-[var(--color-off-white)]"
                >
                  {link.label}
                </Link>
              ))}
              <div className="mt-4 flex flex-col gap-3">
                <span className="font-mono text-xs uppercase tracking-[0.12em] text-[var(--color-muted)]">
                  Services
                </span>
                {services.map((service) => (
                  <Link
                    key={service.slug}
                    href={`/services/${service.slug}`}
                    className="font-mono text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-off-white)]"
                  >
                    {service.shortName}
                  </Link>
                ))}
              </div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
