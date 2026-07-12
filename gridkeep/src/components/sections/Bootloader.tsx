"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";

const BOOT_LINES = [
  "GRIDKEEP SYSTEM CORE — INITIALIZING",
  "LOADING AI INFERENCE MODULES ......... OK",
  "LOADING AUTOMATION CELLS .............. OK",
  "LOADING SOFTWARE ARCHITECTURE ......... OK",
  "LOADING SECURITY LAYER ................ OK",
  "LOADING CLOUD INFRASTRUCTURE .......... OK",
  "ESTABLISHING FOUNDER-LED CONTROL ...... OK",
  "SYSTEM STATUS: OPERATIONAL",
];

const CURSOR_DELAY_S = BOOT_LINES.length * 0.16 + 0.3;

export default function Bootloader() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const lines = Array.from(el.querySelectorAll<HTMLElement>("[data-boot-line]"));
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduced) {
      gsap.set(lines, { opacity: 1 });
      return;
    }

    const tl = gsap.timeline();
    lines.forEach((line, i) => {
      tl.fromTo(
        line,
        { opacity: 0, x: -8 },
        { opacity: 1, x: 0, duration: 0.28, ease: "power1.out" },
        i * 0.16
      );
    });

    return () => {
      tl.kill();
    };
  }, []);

  return (
    <section
      aria-label="System boot sequence"
      className="gk-grid-bg gk-scanline flex min-h-[38vh] flex-col justify-center border-b border-gk-graphite bg-gk-black px-5 py-16 sm:px-8"
    >
      <div ref={containerRef} className="mx-auto w-full max-w-3xl font-mono-tech text-xs sm:text-sm">
        {BOOT_LINES.map((line, i) => (
          <p
            key={line}
            data-boot-line
            className={`py-0.5 opacity-0 ${
              i === BOOT_LINES.length - 1 ? "mt-2 text-gk-orange" : "text-gk-grey"
            }`}
          >
            <span className="text-gk-grey-dim">[{String(i).padStart(2, "0")}]</span> {line}
          </p>
        ))}
        <p
          className="mt-4 h-4 w-2 animate-pulse bg-gk-orange opacity-0"
          style={{ animationDelay: `${CURSOR_DELAY_S}s` }}
          aria-hidden="true"
        />
      </div>
    </section>
  );
}
