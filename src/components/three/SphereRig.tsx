"use client";

import { Suspense, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";
import { OrbitRings } from "./OrbitRings";
import { PlasmaColumn } from "./PlasmaColumn";
import { CoreModel } from "./CoreModel";
import { ElectricArcs } from "./ElectricArcs";
import { HoverPulseController } from "./HoverPulseController";
import { Pedestal } from "./Pedestal";

// A full 360° spin necessarily sweeps through every azimuthal angle —
// and this asset's two blades don't form a closed cage around the core
// sphere, so several of those angles leave a large arc of it exposed
// above/beside the blades no matter how the core itself is positioned
// vertically (Y-rotation can't fix a coverage gap, only move which gap
// faces the camera). Oscillating within a curated arc instead keeps the
// spin alive without ever visiting the angles where that gap opens up.
// Found empirically by sampling renders across a spin cycle — see the
// screenshots referenced in the commit that added this.
const ROTATION_CENTER = THREE.MathUtils.degToRad(10);
const ROTATION_AMPLITUDE = THREE.MathUtils.degToRad(7);

export function SphereRig() {
  const groupRef = useRef<THREE.Group>(null);
  const oscTime = useRef(0);

  useFrame((_, delta) => {
    if (groupRef.current) {
      oscTime.current += delta * sceneState.rotationSpeed;
      groupRef.current.rotation.y = ROTATION_CENTER + Math.sin(oscTime.current) * ROTATION_AMPLITUDE;
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
      <ElectricArcs />
      <OrbitRings />
      <PlasmaColumn />
      <Pedestal />
      <HoverPulseController />
    </group>
  );
}
