"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Edges } from "@react-three/drei";
import * as THREE from "three";
import { METAL } from "../materialHooks";

export default function ArchitectureMesh({ scale = 1 }: { scale?: number }) {
  const group = useRef<THREE.Group>(null);

  const layers = useMemo(() => {
    const count = 6;
    return new Array(count).fill(0).map((_, i) => ({
      y: i * 0.42 - 1.1,
      w: 1.8 - i * 0.08,
      active: i % 2 === 0,
    }));
  }, []);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.12;
  });

  return (
    <group ref={group} scale={scale}>
      {layers.map((l, i) => (
        <group key={i} position={[0, l.y, 0]}>
          <mesh castShadow receiveShadow>
            <boxGeometry args={[l.w, 0.3, l.w]} />
            <meshStandardMaterial {...METAL.gunmetal} />
            <Edges color={l.active ? "#FF5A00" : "#6E2200"} />
          </mesh>
          {l.active && (
            <mesh position={[l.w / 2 + 0.15, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.03, 0.03, 0.3, 8]} />
              <meshStandardMaterial color="#FF7A1A" emissive="#FF5A00" emissiveIntensity={1} />
            </mesh>
          )}
        </group>
      ))}
      <mesh position={[0, -1.5, 0]}>
        <cylinderGeometry args={[0.3, 0.3, 0.22, 20]} />
        <meshStandardMaterial color="#FF5A00" emissive="#FF5A00" emissiveIntensity={1.3} />
      </mesh>
      <pointLight color="#FF7A1A" intensity={3.5} distance={4} decay={2} position={[0, 0, 1]} />
    </group>
  );
}
