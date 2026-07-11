"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import { useCoreGlowMaterial, METAL } from "../materialHooks";

export default function NeuralMesh({ scale = 1 }: { scale?: number }) {
  const group = useRef<THREE.Group>(null);
  const coreMat = useCoreGlowMaterial("#FF7A1A", 1.4);

  const nodes = useMemo(() => {
    const count = 9;
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i < count; i++) {
      const phi = Math.acos(1 - (2 * (i + 0.5)) / count);
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;
      const r = 1.7;
      pts.push(new THREE.Vector3(r * Math.sin(phi) * Math.cos(theta), r * Math.sin(phi) * Math.sin(theta), r * Math.cos(phi)));
    }
    return pts;
  }, []);

  const edges = useMemo(() => {
    const lines: [THREE.Vector3, THREE.Vector3][] = [];
    nodes.forEach((n, i) => {
      lines.push([new THREE.Vector3(0, 0, 0), n]);
      const next = nodes[(i + 2) % nodes.length];
      lines.push([n, next]);
    });
    return lines;
  }, [nodes]);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.16;
  });

  return (
    <group ref={group} scale={scale}>
      <mesh>
        <icosahedronGeometry args={[0.4, 1]} />
        <primitive object={coreMat} attach="material" />
      </mesh>
      {nodes.map((n, i) => (
        <mesh key={i} position={n} castShadow>
          <sphereGeometry args={[0.16, 16, 16]} />
          <meshStandardMaterial {...METAL.gunmetal} emissive="#FF5A00" emissiveIntensity={i % 2 === 0 ? 0.9 : 0.15} />
        </mesh>
      ))}
      {edges.map((e, i) => (
        <Line key={i} points={e} color="#C94700" lineWidth={1} transparent opacity={0.55} />
      ))}
      <pointLight color="#FF5A00" intensity={4} distance={5} decay={2} />
    </group>
  );
}
