"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive, copperContact } from "../materials";
import { BoltField, VentField } from "../Instanced";
import { CableRun, StatusLight, DataPulse } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const MODULE_COUNT = 4;

export default function AIInferenceNode({ progressRef, hover = 0 }: { progressRef?: ProgressRef; hover?: number }) {
  const chassisMat = useMemo(() => gunmetal(), []);
  const moduleMat = useMemo(() => darkAnodized(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const contactMat = useMemo(() => copperContact(), []);

  const moduleRefs = useRef<Array<THREE.Group | null>>([]);
  const coreRef = useRef<THREE.Mesh>(null);
  const fanRefs = useRef<Array<THREE.Mesh | null>>([]);

  const boltRow = useMemo(() => Array.from({ length: 6 }, (_, i) => [-0.55 + i * 0.22, 0.42, 0.201] as [number, number, number]), []);

  useFrame((state, delta) => {
    const progress = progressRef?.current.value ?? 0.5;
    const t = state.clock.elapsedTime;

    moduleRefs.current.forEach((m, i) => {
      if (!m) return;
      const active = Math.sin(t * 1.4 - i * 1.1) * 0.5 + 0.5;
      const mat = (m.children[0] as THREE.Mesh)?.material as THREE.MeshStandardMaterial | undefined;
      if (mat && "emissiveIntensity" in mat) {
        mat.emissiveIntensity = 0.6 + active * 1.8 + progress * 1.2;
      }
    });

    if (coreRef.current) {
      coreRef.current.rotation.y += delta * 0.5;
      const mat = coreRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = 1.8 + Math.sin(t * 2) * 0.6 + hover * 1.4;
    }

    fanRefs.current.forEach((f, i) => {
      if (!f) return;
      f.rotation.z += delta * (3 + i * 0.4);
    });
  });

  return (
    <group>
      {/* main chassis */}
      <mesh material={chassisMat} castShadow receiveShadow>
        <boxGeometry args={[1.5, 0.9, 0.4]} />
      </mesh>
      <BoltField positions={boltRow} radius={0.014} length={0.03} />

      {/* mounting rails */}
      <mesh position={[0, -0.5, 0]} material={railMat} castShadow>
        <boxGeometry args={[1.7, 0.06, 0.5]} />
      </mesh>

      {/* removable compute modules slotted into chassis face */}
      {Array.from({ length: MODULE_COUNT }).map((_, i) => {
        const x = -0.54 + i * 0.36;
        return (
          <group
            key={i}
            position={[x, 0.05, 0.22]}
            ref={(el) => {
              moduleRefs.current[i] = el;
            }}
          >
            <mesh material={moduleMat} castShadow>
              <boxGeometry args={[0.3, 0.62, 0.06]} />
            </mesh>
            <mesh position={[0, 0, 0.035]} material={orangeEmissive(1.2)}>
              <boxGeometry args={[0.24, 0.02, 0.005]} />
            </mesh>
          </group>
        );
      })}

      {/* central inference core visible through a service window */}
      <mesh ref={coreRef} position={[0, -0.32, 0.24]} material={orangeEmissive(1.8)}>
        <octahedronGeometry args={[0.09, 0]} />
      </mesh>

      {/* liquid cooling lines */}
      <CableRun points={[[-0.75, 0.3, 0.1], [-0.9, 0.55, 0.05], [-0.6, 0.68, 0.02]]} radius={0.02} color="#101418" />
      <CableRun points={[[0.75, 0.3, 0.1], [0.9, 0.55, 0.05], [0.6, 0.68, 0.02]]} radius={0.02} color="#101418" />

      {/* fiber / data bus connectors on the side */}
      <group position={[0.76, -0.1, 0]}>
        {Array.from({ length: 5 }).map((_, i) => (
          <mesh key={i} position={[0, 0.3 - i * 0.15, 0]} rotation={[0, 0, Math.PI / 2]} material={contactMat} castShadow>
            <cylinderGeometry args={[0.02, 0.02, 0.08, 8]} />
          </mesh>
        ))}
      </group>

      {/* airflow vents + fans */}
      <group position={[-0.76, -0.1, 0]}>
        <VentField rows={5} cols={2} cellSize={0.05} gap={0.08} plane="xy" />
      </group>
      {[0.5, -0.5].map((x, i) => (
        <mesh
          key={i}
          position={[x, -0.5, -0.22]}
          rotation={[0, 0, 0]}
          ref={(el) => {
            fanRefs.current[i] = el;
          }}
        >
          <torusGeometry args={[0.09, 0.014, 8, 4]} />
          <meshStandardMaterial color="#0b0b0b" metalness={0.6} roughness={0.5} />
        </mesh>
      ))}

      {/* status indicators */}
      <StatusLight position={[-0.68, 0.4, 0.21]} offset={0} />
      <StatusLight position={[-0.6, 0.4, 0.21]} offset={0.6} />
      <StatusLight position={[0.68, 0.4, 0.21]} offset={1.1} />

      {/* data traveling through the bus into the core */}
      <DataPulse from={[-0.54, 0.05, 0.26]} to={[0, -0.32, 0.24]} speed={0.45} />
      <DataPulse from={[0.54, 0.05, 0.26]} to={[0, -0.32, 0.24]} speed={0.4} delay={0.5} />
      <DataPulse from={[0, -0.32, 0.24]} to={[0.76, -0.1, 0.1]} speed={0.5} delay={0.25} />

      {/* base plate */}
      <mesh position={[0, -0.58, 0]} material={railMat} castShadow receiveShadow>
        <boxGeometry args={[1.75, 0.04, 0.6]} />
      </mesh>
    </group>
  );
}
