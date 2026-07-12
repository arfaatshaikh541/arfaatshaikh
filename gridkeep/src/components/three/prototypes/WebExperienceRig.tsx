"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive } from "../materials";
import { VentField } from "../Instanced";
import { StatusLight } from "../Parts";
import { createSchematicTexture } from "../canvasTexture";
import type { ProgressRef } from "@/hooks/useScrollProgress";

export default function WebExperienceRig({
  progressRef,
}: {
  progressRef?: ProgressRef;
  hover?: number;
}) {
  const frameMat = useMemo(() => gunmetal(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const panelMat = useMemo(() => darkAnodized(), []);
  const panelRef = useRef<THREE.Group>(null);
  const camArm = useRef<THREE.Group>(null);
  const [screenTex, setScreenTex] = useState<THREE.CanvasTexture | null>(null);

  useEffect(() => {
    setScreenTex(createSchematicTexture());
  }, []);

  useFrame((state) => {
    const progress = progressRef?.current.value ?? 0.5;
    // desktop (wide) -> tablet -> mobile (narrow), driven by scroll progress
    const width = progress < 0.5
      ? THREE.MathUtils.lerp(1.5, 0.95, progress / 0.5)
      : THREE.MathUtils.lerp(0.95, 0.55, (progress - 0.5) / 0.5);

    if (panelRef.current) {
      const current = panelRef.current.scale.x;
      panelRef.current.scale.x = THREE.MathUtils.lerp(current, width, 0.08);
    }
    if (camArm.current) {
      camArm.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.4) * 0.15;
    }
  });

  return (
    <group>
      {/* mounting rail */}
      <mesh position={[0, -0.85, 0]} material={frameMat} castShadow receiveShadow>
        <boxGeometry args={[2.2, 0.08, 0.3]} />
      </mesh>
      {[-0.9, 0.9].map((x, i) => (
        <mesh key={i} position={[x, -0.4, 0]} material={orangeEmissive(1)}>
          <boxGeometry args={[0.02, 0.7, 0.02]} />
        </mesh>
      ))}

      {/* articulated mounting arm */}
      <group position={[0, -0.8, 0]}>
        <mesh material={railMat} castShadow>
          <cylinderGeometry args={[0.06, 0.06, 0.14, 10]} />
        </mesh>
        <mesh position={[0, 0.35, 0]} material={railMat} castShadow>
          <boxGeometry args={[0.05, 0.7, 0.05]} />
        </mesh>
      </group>

      {/* responsive display panel */}
      <group ref={panelRef} position={[0, 0.05, 0]}>
        <mesh material={panelMat} castShadow receiveShadow>
          <boxGeometry args={[1, 0.68, 0.05]} />
        </mesh>
        {screenTex && (
          <mesh position={[0, 0, 0.03]}>
            <planeGeometry args={[0.92, 0.6]} />
            <meshStandardMaterial map={screenTex} emissiveMap={screenTex} emissive="#2a0f05" emissiveIntensity={0.6} />
          </mesh>
        )}
        {/* calibration markers at corners */}
        {[
          [-0.46, 0.3],
          [0.46, 0.3],
          [-0.46, -0.3],
          [0.46, -0.3],
        ].map(([x, y], i) => (
          <mesh key={i} position={[x, y, 0.032]} material={orangeEmissive(1.6)}>
            <ringGeometry args={[0.012, 0.018, 12]} />
          </mesh>
        ))}
      </group>

      {/* camera tracking module on its own arm */}
      <group ref={camArm} position={[0, 0.75, 0.3]}>
        <mesh material={frameMat} castShadow>
          <boxGeometry args={[0.14, 0.1, 0.14]} />
        </mesh>
        <mesh position={[0, -0.06, 0.06]}>
          <sphereGeometry args={[0.025, 10, 10]} />
          <meshPhysicalMaterial color="#050505" roughness={0.05} transmission={0.7} thickness={0.2} />
        </mesh>
      </group>

      {/* GPU rendering module at the base */}
      <group position={[0, -1.1, 0.15]}>
        <mesh material={frameMat} castShadow receiveShadow>
          <boxGeometry args={[0.9, 0.22, 0.4]} />
        </mesh>
        <VentField rows={3} cols={8} cellSize={0.03} gap={0.05} center={[0, 0, 0.21]} />
        <StatusLight position={[0.38, 0, 0.21]} offset={0} />
      </group>

      {/* interaction sensor bars */}
      {[-1, 1].map((x, i) => (
        <mesh key={i} position={[x * 0.7, 0.4, 0.28]} material={railMat} castShadow>
          <boxGeometry args={[0.05, 0.05, 0.15]} />
        </mesh>
      ))}
    </group>
  );
}
