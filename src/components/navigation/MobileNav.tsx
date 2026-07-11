"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { NAV_LINKS } from "@/lib/constants";

interface MobileNavProps {
  open: boolean;
  onClose: () => void;
}

export function MobileNav({ open, onClose }: MobileNavProps) {
  useEffect(() => {
    if (!open) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-50 flex flex-col bg-black md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Site navigation"
        >
          <div className="flex items-center justify-between border-b border-line px-6 py-5">
            <span className="font-display text-lg tracking-widest2 text-warm">GRIDKEEP</span>
            <button
              type="button"
              onClick={onClose}
              className="font-mono text-xs uppercase tracking-widest2 text-orange"
            >
              Close
            </button>
          </div>
          <nav className="flex flex-1 flex-col justify-center gap-2 px-6" aria-label="Mobile">
            {NAV_LINKS.map((link, index) => (
              <motion.div
                key={link.href}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 * index, duration: 0.3 }}
              >
                <Link
                  href={link.href}
                  onClick={onClose}
                  className="block border-b border-line py-4 font-display text-3xl text-warm transition-colors hover:text-orange"
                >
                  {link.label}
                </Link>
              </motion.div>
            ))}
          </nav>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
