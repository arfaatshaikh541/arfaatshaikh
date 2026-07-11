"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useCoreGlowMaterial, METAL } from "../materialHooks";

export default function VaultMesh({ scale = 1 }: { scale?: number }) {
  const shellA = useRef<THREE.Group>(null);
  const shellB = useRef<THREE.Group>(null);
  const scanRef = useRef<THREE.Mesh>(null);
  const coreMat = useCoreGlowMaterial("#FF5A00", 1.7);

  useFrame((state, delta) => {
    if (shellA.current) shellA.current.rotation.z += delta * 0.1;
    if (shellB.current) shellB.current.rotation.z -= delta * 0.16;
    if (scanRef.current) scanRef.current.rotation.x = state.clock.elapsedTime * 0.7;
  });

  return (
    <group scale={scale}>
      <group ref={shellA}>
        <mesh castShadow receiveShadow>
          <torusGeometry args={[2.1, 0.22, 8, 40]} />
          <meshStandardMaterial {...METAL.black} />
        </mesh>
        {new Array(8).fill(0).map((_, i) => {
          const a = (i / 8) * Math.PI * 2;
          return (
            <mesh key={i} position={[Math.cos(a) * 2.1, Math.sin(a) * 2.1, 0]} rotation={[0, 0, a]}>
              <boxGeometry args={[0.2, 0.42, 0.22]} />
              <meshStandardMaterial {...METAL.gunmetal} />
            </mesh>
          );
        })}
      </group>
      <group ref={shellB}>
        <mesh castShadow>
          <torusGeometry args={[1.5, 0.1, 8, 40]} />
          <meshStandardMaterial {...METAL.brushed} />
        </mesh>
      </group>
      <mesh ref={scanRef}>
        <torusGeometry args={[1.1, 0.01, 4, 48]} />
        <meshBasicMaterial color="#FF7A1A" transparent opacity={0.7} />
      </mesh>
      <mesh>
        <cylinderGeometry args={[0.55, 0.55, 0.4, 6]} />
        <primitive object={coreMat} attach="material" />
      </mesh>
      <pointLight color="#FF5A00" intensity={5} distance={5} decay={2} />
    </group>
  );
}
