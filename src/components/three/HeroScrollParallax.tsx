"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { sceneState } from "@/lib/sceneStore";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

// Values match the sceneState defaults in sceneStore.ts — the model sits
// exactly where it already does until the visitor starts scrolling.
const FROM = { camZ: 6.2, rotationSpeed: 0.06, targetY: 0, turbulence: 0.15, bladeOpen: 0.08 };
const TO = { camZ: 5.3, rotationSpeed: 0.19, targetY: 0.16, turbulence: 0.4, bladeOpen: 0.26 };

/**
 * Renders nothing itself — locates the nearest <section> ancestor (the
 * Hero) and drives sceneState from that section's own scroll progress, so
 * the model spins up, tilts, and stirs as the hero scrolls past instead of
 * sitting inert. Kept separate from the retired ChapterScroll: no pin, no
 * text repositioning, just a scrub tied to the hero's natural scroll-out.
 */
export function HeroScrollParallax() {
  const markerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const section = markerRef.current?.closest("section");
    if (!section) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const trigger = ScrollTrigger.create({
      trigger: section,
      start: "top top",
      end: "bottom top",
      scrub: 0.4,
      onUpdate: (self) => {
        const p = self.progress;
        sceneState.camZ = gsap.utils.interpolate(FROM.camZ, TO.camZ, p);
        sceneState.rotationSpeed = gsap.utils.interpolate(FROM.rotationSpeed, TO.rotationSpeed, p);
        sceneState.targetY = gsap.utils.interpolate(FROM.targetY, TO.targetY, p);
        sceneState.turbulence = gsap.utils.interpolate(FROM.turbulence, TO.turbulence, p);
        sceneState.bladeOpen = gsap.utils.interpolate(FROM.bladeOpen, TO.bladeOpen, p);
      },
      onLeaveBack: () => {
        sceneState.camZ = FROM.camZ;
        sceneState.rotationSpeed = FROM.rotationSpeed;
        sceneState.targetY = FROM.targetY;
        sceneState.turbulence = FROM.turbulence;
        sceneState.bladeOpen = FROM.bladeOpen;
      },
    });

    return () => trigger.kill();
  }, []);

  return <div ref={markerRef} aria-hidden="true" className="hidden" />;
}
