"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive } from "../materials";
import { BoltField } from "../Instanced";
import { StatusLight, DataPulse } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const MODULES = [
  { label: "API Gateway", y: 0.42 },
  { label: "Auth", y: 0.28 },
  { label: "App Services", y: 0.14 },
  { label: "Database Core", y: 0 },
  { label: "Message Queue", y: -0.14 },
  { label: "Analytics", y: -0.28 },
  { label: "Logging", y: -0.42 },
];

export default function SoftwareRack({ progressRef, hover = 0 }: { progressRef?: ProgressRef; hover?: number }) {
  const frameMat = useMemo(() => gunmetal(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const moduleMat = useMemo(() => darkAnodized(), []);
  const slotRefs = useRef<Array<THREE.Group | null>>([]);

  useFrame((state) => {
    const progress = progressRef?.current.value ?? 0.6 + hover * 0.3;
    slotRefs.current.forEach((slot, i) => {
      if (!slot) return;
      const arrive = THREE.MathUtils.clamp(progress * MODULES.length - i, 0, 1);
      const eased = arrive * arrive * (3 - 2 * arrive);
      slot.position.z = THREE.MathUtils.lerp(0.8, 0, eased);
      const led = slot.children.find((c) => c.name === "led") as THREE.Mesh | undefined;
      if (led) {
        const mat = led.material as THREE.MeshStandardMaterial;
        mat.emissiveIntensity = eased > 0.5 ? 2 + Math.sin(state.clock.elapsedTime * 3 + i) * 0.6 : 0.2;
      }
    });
  });

  return (
    <group>
      {/* rack frame */}
      <mesh material={frameMat} castShadow receiveShadow>
        <boxGeometry args={[1, 1.15, 0.5]} />
      </mesh>
      {[-0.48, 0.48].map((x, i) => (
        <mesh key={i} position={[x, 0, 0.26]} material={railMat} castShadow>
          <boxGeometry args={[0.04, 1.15, 0.04]} />
        </mesh>
      ))}

      {MODULES.map((mod, i) => (
        <group
          key={mod.label}
          position={[0, mod.y, 0]}
          ref={(el) => {
            slotRefs.current[i] = el;
          }}
        >
          <mesh material={moduleMat} castShadow>
            <boxGeometry args={[0.88, 0.11, 0.42]} />
          </mesh>
          <BoltField
            positions={[
              [-0.4, 0, 0.211],
              [0.4, 0, 0.211],
            ]}
            radius={0.01}
            length={0.02}
          />
          <mesh name="led" position={[0.36, 0, 0.22]} material={orangeEmissive(1.4)}>
            <boxGeometry args={[0.04, 0.02, 0.01]} />
          </mesh>
          <mesh position={[-0.36, 0, 0.22]} material={railMat}>
            <boxGeometry args={[0.06, 0.02, 0.01]} />
          </mesh>
        </group>
      ))}

      {/* internal data routes */}
      {MODULES.slice(0, -1).map((mod, i) => (
        <DataPulse
          key={mod.label}
          from={[0.3, mod.y, 0.05]}
          to={[0.3, MODULES[i + 1].y, 0.05]}
          speed={0.7}
          delay={i * 0.15}
        />
      ))}

      {/* cooling channel on the side */}
      <mesh position={[0, 0, -0.27]} material={railMat}>
        <boxGeometry args={[0.9, 1.1, 0.02]} />
      </mesh>

      {/* status rail */}
      <StatusLight position={[-0.42, 0.55, 0.26]} offset={0} />
      <StatusLight position={[0.42, 0.55, 0.26]} offset={0.8} />

      {/* base plinth */}
      <mesh position={[0, -0.62, 0]} material={frameMat} castShadow receiveShadow>
        <boxGeometry args={[1.1, 0.1, 0.6]} />
      </mesh>
    </group>
  );
}
