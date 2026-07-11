"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useCoreGlowMaterial, METAL } from "../materialHooks";

export default function PortalMesh({ scale = 1 }: { scale?: number }) {
  const group = useRef<THREE.Group>(null);
  const coreMat = useCoreGlowMaterial("#FF5A00", 2.1);

  const rings = useMemo(() => new Array(7).fill(0).map((_, i) => ({ z: -i * 0.55, r: 1.1 + i * 0.32 })), []);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.z += delta * 0.05;
  });

  return (
    <group scale={scale}>
      <group ref={group}>
        {rings.map((ring, i) => (
          <mesh key={i} position={[0, 0, ring.z]}>
            <torusGeometry args={[ring.r, 0.045, 8, 48]} />
            <meshStandardMaterial
              {...METAL.black}
              emissive={new THREE.Color("#FF5A00")}
              emissiveIntensity={0.25 + (1 - i / rings.length) * 0.9}
            />
          </mesh>
        ))}
      </group>
      <mesh position={[0, 0, 0.3]}>
        <ringGeometry args={[0.75, 0.95, 48]} />
        <primitive object={coreMat} attach="material" />
      </mesh>
      <pointLight color="#FF5A00" intensity={5} distance={7} decay={2} position={[0, 0, 1]} />
    </group>
  );
}
