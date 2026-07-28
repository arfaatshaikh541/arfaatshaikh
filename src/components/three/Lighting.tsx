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
      coreLightA.current.intensity = (2.4 + Math.sin(t * 2.1) * 0.4) * brightness;
    }
    if (coreLightB.current) {
      coreLightB.current.intensity = (1.8 + Math.sin(t * 1.4 + 1.5) * 0.5) * brightness;
    }
    if (rimLight.current) {
      rimLight.current.intensity = 1.2 + brightness * 0.4;
    }
  });

  return (
    <>
      <ambientLight intensity={0.1} color="#241512" />
      <directionalLight position={[3, 4, 5]} intensity={0.55} color="#f2ede7" />
      <directionalLight position={[-4, -2, 3]} intensity={0.2} color="#ff5a2e" />
      <pointLight ref={coreLightA} position={[0.4, 0.2, 0.3]} color="#ff3b20" distance={5} decay={2} />
      <pointLight ref={coreLightB} position={[-0.3, -0.3, -0.4]} color="#8b0000" distance={4.5} decay={2} />
      <pointLight ref={rimLight} position={[-2.5, 1.5, -3]} color="#ff1a12" distance={8} decay={2} />
    </>
  );
}
