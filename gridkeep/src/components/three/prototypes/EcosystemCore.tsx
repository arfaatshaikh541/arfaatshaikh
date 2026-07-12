"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive } from "../materials";
import { StatusLight, DataPulse } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const NODES = [
  "AI Compute",
  "Automation Cell",
  "Software Rack",
  "Cybersecurity Vault",
  "Cloud Array",
  "Business Hub",
  "Web Experience Lab",
];

export default function EcosystemCore({ progressRef }: { progressRef?: ProgressRef }) {
  const frameMat = useMemo(() => gunmetal(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const moduleMat = useMemo(() => darkAnodized(), []);
  const coreRef = useRef<THREE.Mesh>(null);
  const moduleRefs = useRef<Array<THREE.Group | null>>([]);
  const railRefs = useRef<Array<THREE.Mesh | null>>([]);

  const dockRadius = 1.65;
  const explodedRadius = 3.2;

  const angles = useMemo(
    () => NODES.map((_, i) => (i / NODES.length) * Math.PI * 2),
    []
  );

  useFrame((state) => {
    const progress = progressRef?.current.value ?? 0.6;
    const eased = progress * progress * (3 - 2 * progress);

    if (coreRef.current) {
      coreRef.current.rotation.y += 0.004;
      const mat = coreRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = 1.2 + eased * 2.6 + Math.sin(state.clock.elapsedTime * 2) * 0.3;
    }

    moduleRefs.current.forEach((m, i) => {
      if (!m) return;
      const angle = angles[i];
      const r = THREE.MathUtils.lerp(explodedRadius, dockRadius, eased);
      m.position.x = Math.cos(angle) * r;
      m.position.z = Math.sin(angle) * r;
      m.rotation.y = -angle + Math.PI / 2;
    });

    railRefs.current.forEach((rail, i) => {
      if (!rail) return;
      rail.scale.x = Math.max(0.05, eased);
      void i;
    });
  });

  return (
    <group>
      {/* central control core */}
      <mesh position={[0, 0, 0]} material={frameMat} receiveShadow castShadow>
        <cylinderGeometry args={[0.7, 0.8, 0.4, 32]} />
      </mesh>
      <mesh ref={coreRef} position={[0, 0.35, 0]} material={orangeEmissive(1.6)} castShadow>
        <icosahedronGeometry args={[0.34, 1]} />
      </mesh>
      <mesh position={[0, 0.35, 0]} material={railMat}>
        <torusGeometry args={[0.46, 0.02, 8, 32]} />
      </mesh>

      {/* support frame beneath the core */}
      {[0, 1, 2, 3].map((i) => {
        const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
        return (
          <mesh key={i} position={[Math.cos(a) * 0.5, -0.35, Math.sin(a) * 0.5]} material={railMat} castShadow>
            <cylinderGeometry args={[0.03, 0.03, 0.5, 8]} />
          </mesh>
        );
      })}

      {/* satellite system modules */}
      {NODES.map((label, i) => {
        const angle = angles[i];
        return (
          <group
            key={label}
            position={[Math.cos(angle) * explodedRadius, 0, Math.sin(angle) * explodedRadius]}
            ref={(el) => {
              moduleRefs.current[i] = el;
            }}
          >
            <mesh material={moduleMat} castShadow>
              <boxGeometry args={[0.42, 0.3, 0.28]} />
            </mesh>
            <mesh position={[0, 0.18, 0]} material={orangeEmissive(1.3)}>
              <boxGeometry args={[0.3, 0.02, 0.02]} />
            </mesh>
            <StatusLight position={[0.16, -0.1, 0.15]} offset={i * 0.3} />

            {/* docking rail back to the core */}
            <mesh
              position={[-explodedRadius / 2, -0.12, 0]}
              rotation={[0, -Math.PI / 2, 0]}
              scale={[0.05, 1, 1]}
              ref={(el) => {
                railRefs.current[i] = el;
              }}
              material={railMat}
            >
              <boxGeometry args={[explodedRadius - 0.75, 0.02, 0.02]} />
            </mesh>
          </group>
        );
      })}

      {angles.map((angle, i) => (
        <DataPulse
          key={i}
          from={[Math.cos(angle) * dockRadius, 0, Math.sin(angle) * dockRadius]}
          to={[0, 0, 0]}
          speed={0.4}
          delay={i * 0.14}
        />
      ))}
    </group>
  );
}
