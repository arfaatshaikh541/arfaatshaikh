"use client";

import { useEffect, useRef, type MutableRefObject } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export type ProgressRef = MutableRefObject<{ value: number }>;

let registered = false;

/**
 * Ties a DOM section's scroll position to a mutable ref (not React state) so
 * R3F scenes can read it inside useFrame without re-rendering the tree.
 */
export function useScrollProgress<T extends HTMLElement = HTMLDivElement>(options?: {
  start?: string;
  end?: string;
  scrub?: number | boolean;
}) {
  const sectionRef = useRef<T | null>(null);
  const progressRef: ProgressRef = useRef({ value: 0 });

  useEffect(() => {
    if (!registered) {
      gsap.registerPlugin(ScrollTrigger);
      registered = true;
    }
    if (!sectionRef.current) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const trigger = ScrollTrigger.create({
      trigger: sectionRef.current,
      start: options?.start ?? "top bottom",
      end: options?.end ?? "bottom top",
      scrub: reduced ? false : (options?.scrub ?? 0.6),
      onUpdate: (self) => {
        progressRef.current.value = self.progress;
      },
    });

    if (reduced) progressRef.current.value = 0.5;

    return () => trigger.kill();
  }, [options?.start, options?.end, options?.scrub]);

  return { sectionRef, progressRef };
}
