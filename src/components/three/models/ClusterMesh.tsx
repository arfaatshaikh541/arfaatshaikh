"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import { METAL } from "../materialHooks";

export default function ClusterMesh({ scale = 1 }: { scale?: number }) {
  const group = useRef<THREE.Group>(null);

  const spheres = useMemo(() => {
    const arr: { pos: THREE.Vector3; r: number; hot: boolean }[] = [];
    const count = 11;
    for (let i = 0; i < count; i++) {
      const phi = Math.acos(-1 + (2 * i) / count);
      const theta = Math.sqrt(count * Math.PI) * phi;
      const rad = 1.3;
      arr.push({
        pos: new THREE.Vector3(rad * Math.cos(theta) * Math.sin(phi), rad * Math.sin(theta) * Math.sin(phi), rad * Math.cos(phi)),
        r: 0.14 + Math.random() * 0.1,
        hot: i % 3 === 0,
      });
    }
    return arr;
  }, []);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.15;
  });

  return (
    <group ref={group} scale={scale}>
      <mesh>
        <sphereGeometry args={[0.34, 20, 20]} />
        <meshStandardMaterial color="#FF5A00" emissive="#FF5A00" emissiveIntensity={1.2} />
      </mesh>
      {spheres.map((s, i) => (
        <group key={i}>
          <mesh position={s.pos} castShadow>
            <sphereGeometry args={[s.r, 16, 16]} />
            <meshStandardMaterial {...METAL.gunmetal} emissive={s.hot ? "#FF7A1A" : "#000000"} emissiveIntensity={s.hot ? 0.8 : 0} />
          </mesh>
          <Line points={[[0, 0, 0], s.pos.toArray()]} color="#6E2200" lineWidth={1} transparent opacity={0.5} />
        </group>
      ))}
      <pointLight color="#FF5A00" intensity={3.5} distance={4} decay={2} />
    </group>
  );
}
