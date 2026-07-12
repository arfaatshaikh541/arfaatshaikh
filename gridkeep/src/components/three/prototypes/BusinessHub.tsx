"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive, copperContact } from "../materials";
import { StatusLight, DataPulse } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const MODULES = [
  { label: "CRM", angle: 0 },
  { label: "ERP", angle: (Math.PI * 2) / 5 },
  { label: "Finance", angle: (Math.PI * 4) / 5 },
  { label: "Support", angle: (Math.PI * 6) / 5 },
  { label: "Ops", angle: (Math.PI * 8) / 5 },
];

export default function BusinessHub({ progressRef, hover = 0 }: { progressRef?: ProgressRef; hover?: number }) {
  const frameMat = useMemo(() => gunmetal(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const moduleMat = useMemo(() => darkAnodized(), []);
  const contactMat = useMemo(() => copperContact(), []);
  const coreRef = useRef<THREE.Mesh>(null);
  const bridgeRefs = useRef<Array<THREE.Mesh | null>>([]);

  const radius = 0.62;

  useFrame((state) => {
    const progress = progressRef?.current.value ?? 0.6 + hover * 0.3;
    if (coreRef.current) {
      coreRef.current.rotation.y += 0.005;
      const mat = coreRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = 1.6 + progress * 2 + Math.sin(state.clock.elapsedTime * 2) * 0.4;
    }
    bridgeRefs.current.forEach((bridge, i) => {
      if (!bridge) return;
      const target = 0.4 + progress * 0.6;
      bridge.scale.x = THREE.MathUtils.lerp(bridge.scale.x, target, 0.05);
      void i;
    });
  });

  return (
    <group>
      {/* base ring platform */}
      <mesh position={[0, -0.5, 0]} material={frameMat} receiveShadow castShadow>
        <cylinderGeometry args={[1.05, 1.1, 0.08, 32]} />
      </mesh>

      {/* central synchronization processor */}
      <mesh ref={coreRef} material={orangeEmissive(1.8)} castShadow>
        <dodecahedronGeometry args={[0.22, 0]} />
      </mesh>
      <mesh material={railMat} castShadow>
        <torusGeometry args={[0.3, 0.02, 8, 24]} />
      </mesh>

      {MODULES.map((mod, i) => {
        const x = Math.cos(mod.angle) * radius;
        const z = Math.sin(mod.angle) * radius;
        return (
          <group key={mod.label} position={[x, 0, z]}>
            <mesh material={moduleMat} castShadow rotation={[0, -mod.angle, 0]}>
              <boxGeometry args={[0.26, 0.32, 0.14]} />
            </mesh>
            <mesh position={[0, 0.22, 0]} rotation={[0, -mod.angle, 0]} material={orangeEmissive(1.2)}>
              <boxGeometry args={[0.2, 0.02, 0.01]} />
            </mesh>
            {[0.06, -0.06].map((dx, j) => (
              <mesh
                key={j}
                position={[Math.cos(mod.angle + Math.PI / 2) * dx, -0.22, Math.sin(mod.angle + Math.PI / 2) * dx]}
                rotation={[Math.PI / 2, 0, 0]}
                material={contactMat}
              >
                <cylinderGeometry args={[0.012, 0.012, 0.05, 6]} />
              </mesh>
            ))}
            {/* integration bridge extending toward the core */}
            <mesh
              position={[-x / 2, 0, -z / 2]}
              rotation={[0, -mod.angle + Math.PI / 2, 0]}
              scale={[0.4, 1, 1]}
              ref={(el) => {
                bridgeRefs.current[i] = el;
              }}
              material={railMat}
            >
              <boxGeometry args={[radius - 0.32, 0.02, 0.02]} />
            </mesh>
          </group>
        );
      })}

      {MODULES.map((mod, i) => (
        <DataPulse
          key={mod.label}
          from={[Math.cos(mod.angle) * (radius - 0.15), 0, Math.sin(mod.angle) * (radius - 0.15)]}
          to={[0, 0, 0]}
          speed={0.5}
          delay={i * 0.2}
        />
      ))}

      <StatusLight position={[0, 0.5, 0]} scale={1.2} offset={0} />
    </group>
  );
}
