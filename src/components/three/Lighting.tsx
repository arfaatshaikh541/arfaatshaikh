"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

export function Lighting() {
  const coreLightA = useRef<THREE.PointLight>(null);
  const coreLightB = useRef<THREE.PointLight>(null);
  const rimLight = useRef<THREE.PointLight>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const brightness =
      sceneState.coreBrightness + sceneState.hoverIntensity * 0.5 + sceneState.pulseStrength * 1.4;

    if (coreLightA.current) {
      coreLightA.current.intensity = (1.6 + Math.sin(t * 2.1) * 0.3) * brightness;
    }
    if (coreLightB.current) {
      coreLightB.current.intensity = (1.2 + Math.sin(t * 1.4 + 1.5) * 0.35) * brightness;
    }
    if (rimLight.current) {
      rimLight.current.intensity = 0.5 + brightness * 0.25;
    }
  });

  return (
    <>
      {/* Neutral key/fill lighting so the model's own dark gunmetal reads as
          gunmetal, not tinted red — only the point lights below (standing in
          for light escaping the cracks) are colored, and are kept short-range
          so that color stays a localized accent instead of flooding the
          whole silhouette. */}
      <ambientLight intensity={0.12} color="#161616" />
      <directionalLight position={[3, 4, 5]} intensity={0.55} color="#f2ede7" />
      <directionalLight position={[-4, -2, 3]} intensity={0.25} color="#6a6a70" />
      <pointLight ref={coreLightA} position={[0.4, 0.2, 0.3]} color="#ff3b20" distance={2.4} decay={2} />
      <pointLight ref={coreLightB} position={[-0.3, -0.3, -0.4]} color="#8b0000" distance={2.2} decay={2} />
      <pointLight ref={rimLight} position={[-2.5, 1.5, -3]} color="#ff1a12" distance={3.5} decay={2} />
    </>
  );
}
