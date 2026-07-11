"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { METAL } from "../materialHooks";

export default function CloudMesh({ scale = 1 }: { scale?: number }) {
  const ring = useRef<THREE.Group>(null);

  const rack = useMemo(() => new Array(4).fill(0), []);
  const leds = useMemo(
    () =>
      new Array(4).fill(0).map(() =>
        new Array(3).fill(0).map(() => Math.random() > 0.5)
      ),
    []
  );

  useFrame((_, delta) => {
    if (ring.current) ring.current.rotation.y += delta * 0.2;
  });

  return (
    <group scale={scale}>
      {rack.map((_, i) => (
        <group key={i} position={[0, -0.9 + i * 0.5, 0]}>
          <mesh castShadow receiveShadow>
            <boxGeometry args={[1.6, 0.4, 1.0]} />
            <meshStandardMaterial {...METAL.gunmetal} />
          </mesh>
          {leds[i].map((on, j) => (
            <mesh key={j} position={[-0.65 + j * 0.14, 0, 0.51]}>
              <boxGeometry args={[0.06, 0.06, 0.02]} />
              <meshStandardMaterial
                color={on ? "#FF7A1A" : "#3a2415"}
                emissive={on ? "#FF5A00" : "#000000"}
                emissiveIntensity={on ? 1.2 : 0}
              />
            </mesh>
          ))}
        </group>
      ))}
      <group ref={ring} position={[0, 1.4, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.9, 0.05, 8, 40]} />
          <meshStandardMaterial color="#FF5A00" emissive="#FF5A00" emissiveIntensity={0.9} />
        </mesh>
        <mesh rotation={[Math.PI / 2.4, 0, 0]}>
          <torusGeometry args={[1.1, 0.02, 8, 40]} />
          <meshStandardMaterial color="#C94700" emissive="#C94700" emissiveIntensity={0.6} transparent opacity={0.7} />
        </mesh>
      </group>
      <pointLight color="#FF5A00" intensity={3.5} position={[0, 1.4, 1]} distance={4} decay={2} />
    </group>
  );
}
