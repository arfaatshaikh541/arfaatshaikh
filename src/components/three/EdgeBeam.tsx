"use client";

import { useMemo, useRef } from "react";
import * as THREE from "three";
import "@/components/three/materials";
import { useFrame } from "@react-three/fiber";

interface EdgeBeamProps {
  from: THREE.Vector3;
  to: THREE.Vector3;
  color?: string;
  width?: number;
  speed?: number;
  active?: boolean;
}

export function EdgeBeam({ from, to, color = "#FF5A00", width = 0.03, speed = 0.6, active = true }: EdgeBeamProps) {
  const mat = useRef<any>(null);

  const { position, quaternion, length } = useMemo(() => {
    const direction = new THREE.Vector3().subVectors(to, from);
    const dist = direction.length();
    const mid = new THREE.Vector3().addVectors(from, to).multiplyScalar(0.5);
    const quat = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(1, 0, 0),
      direction.clone().normalize()
    );
    return { position: mid, quaternion: quat, length: dist };
  }, [from, to]);

  useFrame((state) => {
    if (mat.current) mat.current.uTime = state.clock.elapsedTime;
  });

  return (
    <mesh position={position} quaternion={quaternion}>
      <planeGeometry args={[length, width]} />
      <pulseLineMaterial
        ref={mat}
        transparent
        depthWrite={false}
        side={THREE.DoubleSide}
        blending={THREE.AdditiveBlending}
        uColor={color}
        uSpeed={speed}
        uActive={active ? 1 : 0.2}
        uPulseCount={Math.max(1, Math.round(length))}
      />
    </mesh>
  );
}
