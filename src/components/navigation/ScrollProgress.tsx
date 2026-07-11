"use client";

import { useEffect, useState } from "react";

export default function ScrollProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(docHeight > 0 ? Math.min(1, scrollTop / docHeight) : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="pointer-events-none fixed left-0 top-[var(--header-height)] z-[70] h-px w-full bg-white/5" aria-hidden="true">
      <div
        className="h-full bg-orange-primary transition-[width] duration-75 ease-linear"
        style={{ width: `${progress * 100}%` }}
      />
    </div>
  );
}
