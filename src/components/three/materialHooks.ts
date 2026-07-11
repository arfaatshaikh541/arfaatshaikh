"use client";

import { useEffect, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { EnergySeamMaterial } from "@/shaders/energySeam";
import { CoreGlowMaterial } from "@/shaders/coreGlow";

export function useEnergySeamMaterial(segments = 18, intensity = 1.2) {
  const material = useMemo(() => {
    const m = new EnergySeamMaterial() as InstanceType<typeof EnergySeamMaterial>;
    m.transparent = true;
    m.blending = THREE.AdditiveBlending;
    m.depthWrite = false;
    m.side = THREE.DoubleSide;
    m.uniforms.uSegments.value = segments;
    m.uniforms.uIntensity.value = intensity;
    return m;
  }, [segments, intensity]);

  useEffect(() => () => material.dispose(), [material]);
  useFrame((state) => {
    material.uniforms.uTime.value = state.clock.elapsedTime;
  });

  return material;
}

export function useCoreGlowMaterial(color = "#FF5A00", intensity = 1.6) {
  const material = useMemo(() => {
    const m = new CoreGlowMaterial() as InstanceType<typeof CoreGlowMaterial>;
    m.transparent = true;
    m.blending = THREE.AdditiveBlending;
    m.depthWrite = false;
    m.uniforms.uColor.value = new THREE.Color(color);
    m.uniforms.uIntensity.value = intensity;
    return m;
  }, [color, intensity]);

  useEffect(() => () => material.dispose(), [material]);
  useFrame((state) => {
    material.uniforms.uTime.value = state.clock.elapsedTime;
  });

  return material;
}

export const METAL = {
  black: { color: "#0d0d0d", metalness: 0.85, roughness: 0.32 },
  gunmetal: { color: "#181818", metalness: 0.75, roughness: 0.42 },
  graphite: { color: "#111111", metalness: 0.6, roughness: 0.5 },
  brushed: { color: "#161616", metalness: 0.9, roughness: 0.22 },
} as const;
