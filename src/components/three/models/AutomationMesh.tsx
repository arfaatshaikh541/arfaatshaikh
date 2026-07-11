"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { METAL } from "../materialHooks";

export default function AutomationMesh({ scale = 1 }: { scale?: number }) {
  const arm = useRef<THREE.Group>(null);
  const forearm = useRef<THREE.Group>(null);
  const packages = useRef<THREE.Group>(null);

  const rail = useMemo(() => new Array(6).fill(0), []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (arm.current) arm.current.rotation.z = Math.sin(t * 0.6) * 0.35;
    if (forearm.current) forearm.current.rotation.z = Math.sin(t * 0.8 + 1) * 0.5 - 0.3;
    if (packages.current) {
      packages.current.children.forEach((child, i) => {
        const mesh = child as THREE.Mesh;
        mesh.position.x = ((t * 0.6 + i * 0.9) % 3.6) - 1.8;
      });
    }
  });

  return (
    <group scale={scale} position={[0, -0.6, 0]}>
      {/* base */}
      <mesh position={[0, -0.3, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.5, 0.6, 0.3, 16]} />
        <meshStandardMaterial {...METAL.black} />
      </mesh>
      {/* arm base rotator */}
      <group ref={arm} position={[0, 0, 0]}>
        <mesh position={[0, 0.55, 0]} castShadow>
          <boxGeometry args={[0.28, 1.1, 0.28]} />
          <meshStandardMaterial {...METAL.gunmetal} />
        </mesh>
        <group ref={forearm} position={[0, 1.1, 0]}>
          <mesh position={[0.55, 0, 0]} castShadow>
            <boxGeometry args={[1.1, 0.22, 0.22]} />
            <meshStandardMaterial {...METAL.brushed} />
          </mesh>
          <mesh position={[1.1, 0, 0]}>
            <boxGeometry args={[0.18, 0.34, 0.34]} />
            <meshStandardMaterial color="#FF5A00" emissive="#FF5A00" emissiveIntensity={1.1} />
          </mesh>
        </group>
      </group>

      {/* conveyor rail */}
      <mesh position={[0, -0.55, 1.4]} rotation={[0, 0, 0]} receiveShadow>
        <boxGeometry args={[4, 0.1, 0.9]} />
        <meshStandardMaterial {...METAL.graphite} />
      </mesh>
      {rail.map((_, i) => (
        <mesh key={i} position={[-1.7 + i * 0.68, -0.49, 1.4]}>
          <boxGeometry args={[0.05, 0.02, 0.9]} />
          <meshStandardMaterial color="#FF7A1A" emissive="#FF5A00" emissiveIntensity={0.6} />
        </mesh>
      ))}
      <group ref={packages}>
        {[0, 1, 2].map((i) => (
          <mesh key={i} position={[-1.8 + i * 1.2, -0.34, 1.4]} castShadow>
            <boxGeometry args={[0.34, 0.34, 0.34]} />
            <meshStandardMaterial color="#111111" emissive="#C94700" emissiveIntensity={0.5} metalness={0.4} roughness={0.5} />
          </mesh>
        ))}
      </group>
      <pointLight color="#FF5A00" intensity={4} position={[1.1, 1.1, 0]} distance={4} decay={2} />
    </group>
  );
}
