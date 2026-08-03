"use client";

import { Suspense, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";
import { Flames } from "./Flames";
import { OrbitRings } from "./OrbitRings";
import { PlasmaColumn } from "./PlasmaColumn";
import { CoreModel } from "./CoreModel";
import { ElectricArcs } from "./ElectricArcs";
import { HoverPulseController } from "./HoverPulseController";
import { Pedestal } from "./Pedestal";

export function SphereRig() {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * sceneState.rotationSpeed;
      groupRef.current.rotation.x = THREE.MathUtils.lerp(
        groupRef.current.rotation.x,
        sceneState.parallaxY * 0.3,
        0.05
      );
      groupRef.current.rotation.z = THREE.MathUtils.lerp(
        groupRef.current.rotation.z,
        sceneState.parallaxX * -0.12,
        0.05
      );
    }
  });

  return (
    <group ref={groupRef}>
      <Suspense fallback={null}>
        <CoreModel />
      </Suspense>
      <Flames />
      <ElectricArcs />
      <OrbitRings />
      <PlasmaColumn />
      <Pedestal />
      <HoverPulseController />
    </group>
  );
}
