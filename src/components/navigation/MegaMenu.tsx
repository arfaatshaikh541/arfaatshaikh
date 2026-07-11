"use client";

import { useId, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { services } from "@/data/services";
import { cn } from "@/lib/utils";

export function MegaMenu() {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const closeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  function openMenu() {
    if (closeTimeout.current) clearTimeout(closeTimeout.current);
    setOpen(true);
  }

  function scheduleClose() {
    closeTimeout.current = setTimeout(() => setOpen(false), 120);
  }

  return (
    <div
      className="relative"
      onMouseEnter={openMenu}
      onMouseLeave={scheduleClose}
      onFocus={openMenu}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node)) setOpen(false);
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          "font-mono text-xs uppercase tracking-widest2 transition-colors",
          open ? "text-orange" : "text-warm hover:text-orange"
        )}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
      >
        Services
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            id={menuId}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="absolute left-1/2 top-full z-40 mt-4 w-[min(90vw,760px)] -translate-x-1/2 border border-line bg-near-black/95 p-6 backdrop-blur-sm"
          >
            <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
              {services.map((service) => (
                <Link
                  key={service.slug}
                  href={`/services/${service.slug}`}
                  className="group flex flex-col gap-1 border border-transparent p-4 transition-colors hover:border-line hover:bg-surface"
                >
                  <span className="font-mono text-[10px] uppercase tracking-widest2 text-orange">
                    {service.eyebrow}
                  </span>
                  <span className="font-display text-lg text-warm group-hover:text-orange-bright">
                    {service.shortName}
                  </span>
                  <span className="text-sm text-muted">{service.summary}</span>
                </Link>
              ))}
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-line pt-4">
              <Link href="/services" className="font-mono text-xs uppercase tracking-widest2 text-orange hover:text-orange-bright">
                View all services →
              </Link>
              <Link href="/gridkeep-system" className="font-mono text-xs uppercase tracking-widest2 text-muted hover:text-orange">
                See the GRIDKEEP System
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
