"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { Sparkles } from "@react-three/drei";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive, orangeGlass } from "../materials";
import { BoltField, circleOfBolts } from "../Instanced";
import { CableRun, StatusLight } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const PETAL_COUNT = 8;

export default function ContactPortalRig({ progressRef }: { progressRef?: ProgressRef }) {
  const shellMat = useMemo(() => gunmetal(), []);
  const petalMat = useMemo(() => darkAnodized(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const glowMat = useMemo(() => orangeGlass(1.8), []);
  const petalRefs = useRef<Array<THREE.Group | null>>([]);
  const glowRef = useRef<THREE.Mesh>(null);

  const boltPositions = useMemo(() => circleOfBolts(20, 1.3), []);

  useFrame((state) => {
    const progress = progressRef?.current.value ?? 0.55;
    const target = -0.1 - progress * 1.0;
    petalRefs.current.forEach((p, i) => {
      if (!p) return;
      p.rotation.x = THREE.MathUtils.lerp(p.rotation.x, target - i * 0.01, 0.08);
    });
    if (glowRef.current) {
      const mat = glowRef.current.material as THREE.MeshPhysicalMaterial;
      mat.emissiveIntensity = 1.2 + progress * 2.6 + Math.sin(state.clock.elapsedTime * 1.6) * 0.3;
    }
  });

  return (
    <group>
      {/* heavy floor platform */}
      <mesh position={[0, -1.35, 0]} material={shellMat} receiveShadow castShadow>
        <cylinderGeometry args={[1.7, 1.85, 0.2, 32]} />
      </mesh>
      <BoltField positions={circleOfBolts(24, 1.6, -1.24)} rotation={[Math.PI / 2, 0, 0]} radius={0.02} length={0.04} />

      {/* outer door housing */}
      <mesh material={shellMat} castShadow receiveShadow>
        <torusGeometry args={[1.3, 0.16, 16, 48]} />
      </mesh>
      <BoltField positions={boltPositions} rotation={[Math.PI / 2, 0, 0]} radius={0.02} length={0.04} />
      <mesh material={orangeEmissive(1.4)}>
        <torusGeometry args={[1.44, 0.02, 8, 48]} />
      </mesh>

      {/* iris door petals */}
      {Array.from({ length: PETAL_COUNT }).map((_, i) => {
        const angle = (i / PETAL_COUNT) * Math.PI * 2;
        return (
          <group key={i} position={[Math.cos(angle) * 0.5, Math.sin(angle) * 0.5, 0.05]} rotation={[0, 0, angle - Math.PI / 2]}>
            <group ref={(el) => { petalRefs.current[i] = el; }}>
              <mesh position={[0, 0.42, 0]} material={petalMat} castShadow receiveShadow>
                <boxGeometry args={[0.42, 0.84, 0.07]} />
              </mesh>
            </group>
          </group>
        );
      })}

      {/* inner glow revealed as the door opens */}
      <mesh ref={glowRef} position={[0, 0, -0.2]} material={glowMat}>
        <circleGeometry args={[0.55, 32]} />
      </mesh>

      {/* locking mechanisms */}
      {[0, 1, 2, 3].map((i) => {
        const a = (i / 4) * Math.PI * 2 + Math.PI / 8;
        return (
          <mesh key={i} position={[Math.cos(a) * 1.1, Math.sin(a) * 1.1, 0.12]} material={railMat} castShadow>
            <boxGeometry args={[0.1, 0.16, 0.06]} />
          </mesh>
        );
      })}

      {/* input console to the side */}
      <group position={[-1.9, -0.6, 0.5]} rotation={[0, 0.35, 0]}>
        <mesh material={darkAnodized()} castShadow>
          <boxGeometry args={[0.5, 0.7, 0.4]} />
        </mesh>
        <mesh position={[0, 0.2, 0.21]} material={orangeEmissive(1)}>
          <planeGeometry args={[0.38, 0.3]} />
        </mesh>
        <StatusLight position={[-0.15, -0.15, 0.21]} offset={0} />
        <StatusLight position={[0.15, -0.15, 0.21]} offset={0.5} />
      </group>

      {/* cables + sensors */}
      <CableRun points={[[-1.6, -1.1, 0.2], [-1.2, -1.3, 0.4], [-0.6, -1.2, 0.5]]} radius={0.025} />
      <CableRun points={[[1.6, -1.1, 0.2], [1.2, -1.3, 0.4], [0.6, -1.2, 0.5]]} radius={0.025} />
      {[-0.9, 0.9].map((x, i) => (
        <mesh key={i} position={[x, 0.9, 0.3]} material={shellMat} castShadow>
          <boxGeometry args={[0.1, 0.1, 0.1]} />
        </mesh>
      ))}

      <Sparkles count={12} scale={[2.4, 1.6, 0.5]} size={1.4} speed={0.2} color="#ff8a44" opacity={0.4} />
    </group>
  );
}
