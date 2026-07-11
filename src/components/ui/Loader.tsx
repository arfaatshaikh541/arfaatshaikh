"use client";

import { useEffect, useState } from "react";

const BOOT_LINES = [
  "INITIALIZING GRIDKEEP SYSTEM",
  "LOADING PROTOTYPE ENVIRONMENT",
  "ACTIVATING SHADERS",
  "ESTABLISHING CONNECTION",
];

const HARD_TIMEOUT_MS = 2600;

export function Loader() {
  const [progress, setProgress] = useState(0);
  const [line, setLine] = useState(BOOT_LINES[0]);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let raf: number;
    const start = performance.now();

    function tick(now: number) {
      const elapsed = now - start;
      const pct = Math.min(100, Math.round((elapsed / 1400) * 100));
      setProgress(pct);
      setLine(BOOT_LINES[Math.min(BOOT_LINES.length - 1, Math.floor((pct / 100) * BOOT_LINES.length))]);
      if (pct < 100 && elapsed < HARD_TIMEOUT_MS) {
        raf = requestAnimationFrame(tick);
      } else {
        setProgress(100);
        window.setTimeout(() => setHidden(true), 320);
      }
    }

    raf = requestAnimationFrame(tick);
    const hardTimeout = window.setTimeout(() => setHidden(true), HARD_TIMEOUT_MS);

    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(hardTimeout);
    };
  }, []);

  return (
    <div
      aria-hidden={hidden}
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black transition-opacity duration-500"
      style={{
        opacity: hidden ? 0 : 1,
        pointerEvents: hidden ? "none" : "auto",
      }}
    >
      <div className="w-64 max-w-[70vw] font-mono text-warm">
        <div className="mb-4 text-xs uppercase tracking-widest2 text-orange">GRIDKEEP</div>
        <div className="mb-3 h-px w-full bg-line" />
        <div className="mb-2 h-1 w-full overflow-hidden bg-surface">
          <div
            className="h-full bg-orange transition-[width] duration-150 ease-linear"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-[10px] uppercase tracking-widest2 text-muted">
          <span>{line}</span>
          <span>{progress}%</span>
        </div>
      </div>
    </div>
  );
}
