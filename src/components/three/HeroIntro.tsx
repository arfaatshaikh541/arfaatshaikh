"use client";

import gsap from "gsap";
import { sceneState } from "@/lib/sceneStore";

// The values sceneState already rests at (sceneStore.ts's own defaults,
// and the same numbers HeroScrollParallax treats as its own "top of hero"
// baseline) — the timeline below animates *toward* these, never away from
// them, so it can never leave the model in a state other components don't
// expect.
const REST = { introScale: 1, coreBrightness: 0.35, turbulence: 0.15, bladeOpen: 0.08, rotationSpeed: 0.06 };

let hasPlayed = false;

/**
 * Plays once — called from CoreModel the moment the GLB has actually
 * loaded and is about to render for the first time, not on Hero mount.
 * The fetch can take anywhere from instant (cached) to a couple of
 * seconds (cold), and triggering on mount would let the whole tween
 * finish before there's a mesh for it to animate.
 *
 * The model grows in from a sliver, the core ignites from dark, blades
 * ease off a fast opening spin, and the camera settles in from a slight
 * pull-back. The pull-back rides on pulseZOffset rather than camZ so it
 * can't fight HeroScrollParallax's onUpdate, which owns camZ from the
 * very first scroll/refresh event. Skipped entirely under reduced
 * motion — the model just renders at rest.
 */
export function playHeroIntro() {
  if (hasPlayed) return;
  hasPlayed = true;
  if (typeof window === "undefined") return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  sceneState.introScale = 0.05;
  sceneState.coreBrightness = 0;
  sceneState.turbulence = 0.05;
  sceneState.bladeOpen = 0.02;
  sceneState.rotationSpeed = 0.34;
  sceneState.pulseZOffset = 2.4;

  gsap
    .timeline()
    .to(sceneState, { introScale: REST.introScale, duration: 1.3, ease: "back.out(1.4)" }, 0)
    .to(sceneState, { pulseZOffset: 0, duration: 1.5, ease: "power3.out" }, 0)
    .to(sceneState, { coreBrightness: REST.coreBrightness, duration: 1.6, ease: "power2.out" }, 0.1)
    .to(
      sceneState,
      { bladeOpen: REST.bladeOpen, turbulence: REST.turbulence, duration: 1.4, ease: "power2.out" },
      0.05
    )
    .to(sceneState, { rotationSpeed: REST.rotationSpeed, duration: 1.8, ease: "power2.out" }, 0.2);
}
