"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import { useCoreGlowMaterial, METAL } from "../materialHooks";
import { ecosystemNodes } from "@/data/ecosystem";

export default function EcosystemMesh({ scale = 1 }: { scale?: number }) {
  const group = useRef<THREE.Group>(null);
  const coreMat = useCoreGlowMaterial("#FF5A00", 1.9);

  const nodes = useMemo(
    () =>
      ecosystemNodes.map((n) => {
        const rad = (n.angle * Math.PI) / 180;
        return { ...n, pos: new THREE.Vector3(Math.cos(rad) * 2.6, Math.sin(rad) * 2.6, 0) };
      }),
    []
  );

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.z += delta * 0.045;
  });

  return (
    <group scale={scale}>
      <mesh>
        <icosahedronGeometry args={[0.6, 2]} />
        <primitive object={coreMat} attach="material" />
      </mesh>
      <pointLight color="#FF5A00" intensity={6} distance={7} decay={2} />
      <group ref={group}>
        {nodes.map((n) => (
          <group key={n.id}>
            <Line points={[[0, 0, 0], n.pos.toArray()]} color="#C94700" lineWidth={1.4} transparent opacity={0.55} />
            <mesh position={n.pos} castShadow>
              <cylinderGeometry args={[0.32, 0.36, 0.22, 8]} />
              <meshStandardMaterial {...METAL.gunmetal} />
            </mesh>
            <mesh position={[n.pos.x, n.pos.y, 0.13]}>
              <torusGeometry args={[0.2, 0.02, 6, 24]} />
              <meshStandardMaterial color="#FF7A1A" emissive="#FF5A00" emissiveIntensity={1} />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  );
}
