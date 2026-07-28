"use client";

import { useEffect, useRef } from "react";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import gsap from "gsap";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

/**
 * An invisible (fully transparent, but still raycastable) hit-test sphere
 * that drives two interactions on top of the scroll-chapter system:
 *   - hover: ramps sceneState.hoverIntensity up/down, picked up by the
 *     core/shell/blade materials to brighten on mouseover.
 *   - click/tap: fires a quick GSAP "energy pulse" — a brief spike in
 *     sceneState.pulseStrength (blades kick outward, core flares, arcs
 *     intensify) plus a small camera punch-in via pulseZOffset.
 */
export function HoverPulseController() {
  const hoverTarget = useRef(0);
  const prefersReducedMotion = useRef(false);

  useEffect(() => {
    prefersReducedMotion.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useFrame(() => {
    sceneState.hoverIntensity = THREE.MathUtils.lerp(
      sceneState.hoverIntensity,
      hoverTarget.current,
      0.08
    );
  });

  const triggerPulse = () => {
    gsap.killTweensOf(sceneState);

    const pulseDuration = prefersReducedMotion.current ? 0.4 : 1;
    const punchAmount = prefersReducedMotion.current ? -0.08 : -0.45;

    gsap
      .timeline()
      .to(sceneState, { pulseStrength: 1, duration: 0.1, ease: "power2.out" })
      .to(sceneState, { pulseStrength: 0, duration: pulseDuration, ease: "power3.out" });

    gsap
      .timeline()
      .to(sceneState, { pulseZOffset: punchAmount, duration: 0.14, ease: "power2.out" })
      .to(sceneState, { pulseZOffset: 0, duration: 0.8, ease: "elastic.out(1, 0.55)" });
  };

  const onEnter = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation();
    hoverTarget.current = 1;
  };

  const onLeave = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation();
    hoverTarget.current = 0;
  };

  const onClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    triggerPulse();
  };

  return (
    <mesh onPointerEnter={onEnter} onPointerLeave={onLeave} onClick={onClick}>
      <sphereGeometry args={[2.35, 24, 24]} />
      <meshBasicMaterial transparent opacity={0} depthWrite={false} />
    </mesh>
  );
}
