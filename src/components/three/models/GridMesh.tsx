"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import { METAL } from "../materialHooks";

export default function GridMesh({ scale = 1 }: { scale?: number }) {
  const group = useRef<THREE.Group>(null);

  const nodes = useMemo(() => {
    const arr: { pos: THREE.Vector3; hot: boolean }[] = [];
    for (let x = -1; x <= 1; x++) {
      for (let y = -1; y <= 1; y++) {
        for (let z = -1; z <= 1; z++) {
          if (Math.abs(x) + Math.abs(y) + Math.abs(z) === 0) continue;
          arr.push({ pos: new THREE.Vector3(x * 0.85, y * 0.85, z * 0.85), hot: (x + y + z) % 2 === 0 });
        }
      }
    }
    return arr;
  }, []);

  const edges = useMemo(() => {
    const lines: [THREE.Vector3, THREE.Vector3][] = [];
    nodes.forEach((a, i) => {
      nodes.forEach((b, j) => {
        if (i >= j) return;
        if (a.pos.distanceTo(b.pos) < 0.9) {
          lines.push([a.pos, b.pos]);
        }
      });
    });
    return lines;
  }, [nodes]);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.14;
  });

  return (
    <group ref={group} scale={scale}>
      {nodes.map((n, i) => (
        <mesh key={i} position={n.pos} castShadow>
          <boxGeometry args={[0.22, 0.22, 0.22]} />
          <meshStandardMaterial {...METAL.gunmetal} emissive={n.hot ? "#FF5A00" : "#000000"} emissiveIntensity={n.hot ? 0.9 : 0} />
        </mesh>
      ))}
      {edges.map((e, i) => (
        <Line key={i} points={e} color="#C94700" lineWidth={1} transparent opacity={0.4} />
      ))}
      <pointLight color="#FF5A00" intensity={3} distance={4} decay={2} />
    </group>
  );
}
