"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive } from "../materials";
import { VentField } from "../Instanced";
import { StatusLight, DataPulse } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const NODE_ROWS = 4;

export default function CloudArray({ progressRef, hover = 0 }: { progressRef?: ProgressRef; hover?: number }) {
  const frameMat = useMemo(() => gunmetal(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const nodeMat = useMemo(() => darkAnodized(), []);
  const failedRef = useRef<THREE.Mesh>(null);
  const nodeLeds = useRef<Array<THREE.Mesh | null>>([]);

  useFrame((state) => {
    const progress = progressRef?.current.value ?? 0.5 + hover * 0.3;
    const t = state.clock.elapsedTime;

    nodeLeds.current.forEach((led, i) => {
      if (!led) return;
      const isFailed = Math.floor(t * 0.25) % NODE_ROWS === i && progress > 0.4;
      const mat = led.material as THREE.MeshStandardMaterial;
      mat.color.set(isFailed ? "#3a1408" : "#b8420f");
      mat.emissive.set(isFailed ? "#3a1408" : "#ff5a1f");
      mat.emissiveIntensity = isFailed ? 0.3 : 1.6 + Math.sin(t * 3 + i) * 0.6;
    });

    if (failedRef.current) {
      failedRef.current.visible = Math.floor(t * 0.25) % NODE_ROWS === 1 && progress > 0.4;
    }
  });

  return (
    <group>
      {/* rack frame */}
      <mesh material={frameMat} castShadow receiveShadow>
        <boxGeometry args={[0.95, 1.1, 0.55]} />
      </mesh>

      {/* hot-swappable compute nodes */}
      {Array.from({ length: NODE_ROWS }).map((_, i) => {
        const y = 0.36 - i * 0.24;
        return (
          <group key={i} position={[0, y, 0.28]}>
            <mesh material={nodeMat} castShadow>
              <boxGeometry args={[0.82, 0.18, 0.02]} />
            </mesh>
            <mesh
              position={[0.34, 0, 0.015]}
              ref={(el) => {
                nodeLeds.current[i] = el;
              }}
              material={orangeEmissive(1.6)}
            >
              <boxGeometry args={[0.03, 0.03, 0.01]} />
            </mesh>
            {Array.from({ length: 6 }).map((_, s) => (
              <mesh key={s} position={[-0.32 + s * 0.11, 0, 0.012]} material={railMat}>
                <boxGeometry args={[0.02, 0.13, 0.005]} />
              </mesh>
            ))}
          </group>
        );
      })}

      {/* isolated / failed node marker */}
      <mesh ref={failedRef} position={[0, 0.12, 0.32]} material={darkAnodized()}>
        <boxGeometry args={[0.86, 0.22, 0.03]} />
      </mesh>

      {/* network switch */}
      <mesh position={[0, -0.5, 0.29]} material={railMat} castShadow>
        <boxGeometry args={[0.86, 0.06, 0.05]} />
      </mesh>

      {/* observability console */}
      <group position={[0.72, 0.1, 0]}>
        <mesh material={frameMat} castShadow>
          <boxGeometry args={[0.06, 0.9, 0.5]} />
        </mesh>
        <mesh position={[0.032, 0.2, 0]} material={orangeEmissive(1)}>
          <planeGeometry args={[0.02, 0.4]} />
        </mesh>
      </group>

      {/* cooling fans + power distribution */}
      <VentField rows={4} cols={2} cellSize={0.05} gap={0.09} center={[-0.5, 0, 0]} plane="xz" />

      {/* traffic paths between nodes */}
      {Array.from({ length: NODE_ROWS - 1 }).map((_, i) => (
        <DataPulse
          key={i}
          from={[0.2, 0.36 - i * 0.24, 0.3]}
          to={[0.2, 0.36 - (i + 1) * 0.24, 0.3]}
          speed={0.9}
          delay={i * 0.2}
        />
      ))}

      {/* cable trays */}
      <mesh position={[0, -0.58, -0.15]} material={railMat}>
        <boxGeometry args={[0.9, 0.03, 0.12]} />
      </mesh>

      <StatusLight position={[-0.42, 0.5, 0.28]} offset={0} />
      <StatusLight position={[0.42, 0.5, 0.28]} offset={0.9} />
    </group>
  );
}
