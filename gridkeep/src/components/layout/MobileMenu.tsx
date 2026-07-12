"use client";

import Link from "next/link";
import { PRIMARY_NAV } from "@/lib/site";

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function MobileMenu({ open, onClose }: Props) {
  return (
    <div
      id="gk-mobile-menu"
      className={`fixed inset-x-0 top-16 z-40 border-b border-gk-steel bg-gk-black transition-[max-height,opacity] duration-300 lg:hidden ${
        open ? "max-h-[80vh] opacity-100" : "pointer-events-none max-h-0 opacity-0"
      } overflow-hidden`}
      aria-hidden={!open}
    >
      <nav aria-label="Mobile" className="flex flex-col gap-1 px-5 py-6">
        {PRIMARY_NAV.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            onClick={onClose}
            className="border-b border-gk-graphite py-3 font-display text-xl text-gk-white hover:text-gk-orange"
          >
            {link.label}
          </Link>
        ))}
        <Link
          href="/contact"
          onClick={onClose}
          className="gk-btn gk-btn-primary mt-4 w-full justify-center"
        >
          Contact
        </Link>
      </nav>
    </div>
  );
}
