"use client";

import { useEffect, useRef, type RefObject } from "react";
import { ensureGsapRegistered, ScrollTrigger } from "@/lib/gsapSetup";

interface ScrollProgressOptions {
  start?: string;
  end?: string;
  pin?: boolean;
}

export function useScrollProgress(
  triggerRef: RefObject<HTMLElement | null>,
  options: ScrollProgressOptions = {}
) {
  const progress = useRef(0);

  useEffect(() => {
    ensureGsapRegistered();
    const element = triggerRef.current;
    if (!element) return;

    const trigger = ScrollTrigger.create({
      trigger: element,
      start: options.start ?? "top bottom",
      end: options.end ?? "bottom top",
      scrub: true,
      pin: options.pin ?? false,
      onUpdate: (self) => {
        progress.current = self.progress;
      },
    });

    return () => trigger.kill();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerRef, options.start, options.end, options.pin]);

  return progress;
}
