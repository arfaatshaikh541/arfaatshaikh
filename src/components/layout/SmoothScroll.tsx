"use client";

import { useEffect, type ReactNode } from "react";
import Lenis from "lenis";
import { ensureGsapRegistered, gsap, ScrollTrigger } from "@/lib/gsapSetup";
import { usePrefersReducedMotion } from "@/lib/performance";

export function SmoothScroll({ children }: { children: ReactNode }) {
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    ensureGsapRegistered();
    if (reducedMotion) return;

    const lenis = new Lenis({
      duration: 1.1,
      smoothWheel: true,
      touchMultiplier: 1.2,
    });

    lenis.on("scroll", ScrollTrigger.update);

    gsap.ticker.add((time) => {
      lenis.raf(time * 1000);
    });
    gsap.ticker.lagSmoothing(0);

    return () => {
      lenis.destroy();
      gsap.ticker.remove((time) => {
        lenis.raf(time * 1000);
      });
    };
  }, [reducedMotion]);

  return <>{children}</>;
}
