"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

interface RingProps {
  radius: number;
  tilt: [number, number, number];
  speed: number;
  segments: number;
}

function EngineeredRing({ radius, tilt, speed, segments }: RingProps) {
  const groupRef = useRef<THREE.Group>(null);
  const materialRefs = useRef<THREE.MeshBasicMaterial[]>([]);

  const arcs = useMemo(() => {
    const gap = 0.22;
    const arcLength = (Math.PI * 2) / segments - gap;
    return Array.from({ length: segments }, (_, i) => {
      const start = (i / segments) * Math.PI * 2;
      return { start, arcLength };
    });
  }, [segments]);

  const nodeAngles = useMemo(
    () => Array.from({ length: 6 }, (_, i) => (i / 6) * Math.PI * 2),
    []
  );

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.z += delta * speed;
    }
    const opacity = sceneState.ringsVisible;
    materialRefs.current.forEach((mat) => {
      if (mat) mat.opacity = THREE.MathUtils.lerp(mat.opacity, opacity * 0.85, 0.08);
    });
    if (groupRef.current) {
      groupRef.current.visible = opacity > 0.02;
    }
  });

  return (
    <group ref={groupRef} rotation={tilt}>
      {arcs.map((arc, i) => (
        <mesh key={i} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[radius, 0.008, 8, 24, arc.arcLength]} />
          <meshBasicMaterial
            ref={(m) => {
              if (m) materialRefs.current[i] = m;
            }}
            color="#ff1a12"
            transparent
            opacity={0}
          />
        </mesh>
      ))}
      {nodeAngles.map((angle, i) => (
        <mesh
          key={`node-${i}`}
          position={[Math.cos(angle) * radius, 0, Math.sin(angle) * radius]}
        >
          <sphereGeometry args={[0.02, 8, 8]} />
          <meshBasicMaterial color="#ff5a2e" transparent opacity={0.9} />
        </mesh>
      ))}
    </group>
  );
}

export function OrbitRings() {
  return (
    <>
      <EngineeredRing radius={2.15} tilt={[0.35, 0, 0.1]} speed={0.05} segments={7} />
      <EngineeredRing radius={2.55} tilt={[-0.5, 0.3, 0]} speed={-0.035} segments={5} />
    </>
  );
}
