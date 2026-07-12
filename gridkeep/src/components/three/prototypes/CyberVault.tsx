"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive, copperContact } from "../materials";
import { BoltField, circleOfBolts } from "../Instanced";
import { StatusLight } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const CYCLE = 5;

export default function CyberVault({ progressRef, hover = 0 }: { progressRef?: ProgressRef; hover?: number }) {
  const shellMat = useMemo(() => gunmetal(), []);
  const doorMat = useMemo(() => darkAnodized(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const contactMat = useMemo(() => copperContact(), []);
  const scanMat = useMemo(() => orangeEmissive(2.4), []);

  const doorRef = useRef<THREE.Group>(null);
  const boltPins = useRef<Array<THREE.Mesh | null>>([]);
  const scanRef = useRef<THREE.Mesh>(null);
  const threatRef = useRef<THREE.Mesh>(null);

  const boltPositions = useMemo(() => circleOfBolts(16, 0.42), []);

  useFrame((state) => {
    const speed = 1 + hover * 0.4 + (progressRef?.current.value ?? 0) * 0.2;
    const t = ((state.clock.elapsedTime * speed) % CYCLE) / CYCLE;

    if (threatRef.current) {
      threatRef.current.position.z = THREE.MathUtils.lerp(1.4, 0.55, Math.min(t / 0.4, 1));
      threatRef.current.visible = t < 0.42;
    }

    const scanning = t > 0.1 && t < 0.42;
    if (scanRef.current) {
      scanRef.current.visible = scanning;
      scanRef.current.position.y = THREE.MathUtils.lerp(0.5, -0.5, ((t - 0.1) / 0.32) % 1);
    }

    const locked = t < 0.55;
    boltPins.current.forEach((pin, i) => {
      if (!pin) return;
      const target = locked ? 0 : -0.06;
      pin.position.z = THREE.MathUtils.lerp(pin.position.z, target, 0.1);
      void i;
    });

    if (doorRef.current) {
      const openTarget = t > 0.42 && t < 0.55 ? 0.18 : 0;
      doorRef.current.position.x = THREE.MathUtils.lerp(doorRef.current.position.x, openTarget, 0.06);
    }
  });

  return (
    <group>
      {/* armored outer shell */}
      <mesh rotation={[Math.PI / 2, 0, 0]} material={shellMat} castShadow receiveShadow>
        <cylinderGeometry args={[0.62, 0.66, 0.5, 24]} />
      </mesh>
      <BoltField positions={boltPositions} rotation={[Math.PI / 2, 0, 0]} radius={0.018} length={0.03} />

      {/* segmented vault door */}
      <group ref={doorRef} position={[0, 0, 0.26]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} material={doorMat} castShadow>
          <cylinderGeometry args={[0.5, 0.5, 0.14, 24]} />
        </mesh>
        {Array.from({ length: 8 }).map((_, i) => {
          const a = (i / 8) * Math.PI * 2;
          return (
            <mesh
              key={i}
              position={[Math.cos(a) * 0.34, Math.sin(a) * 0.34, 0.08]}
              rotation={[Math.PI / 2, 0, 0]}
              ref={(el) => {
                boltPins.current[i] = el;
              }}
              material={railMat}
              castShadow
            >
              <cylinderGeometry args={[0.03, 0.03, 0.16, 8]} />
            </mesh>
          );
        })}
        {/* biometric scanner module */}
        <group position={[0, 0, 0.09]}>
          <mesh material={darkAnodized()} castShadow>
            <boxGeometry args={[0.16, 0.1, 0.03]} />
          </mesh>
          <mesh ref={scanRef} position={[0, 0.5, 0.02]} material={scanMat}>
            <planeGeometry args={[0.13, 0.006]} />
          </mesh>
        </group>
        {/* hardware security module contacts */}
        {[-0.12, 0, 0.12].map((x, i) => (
          <mesh key={i} position={[x, -0.3, 0.075]} rotation={[Math.PI / 2, 0, 0]} material={contactMat}>
            <cylinderGeometry args={[0.012, 0.012, 0.02, 8]} />
          </mesh>
        ))}
      </group>

      {/* threat object approaching */}
      <mesh ref={threatRef} position={[0, 0, 1.4]} material={darkAnodized()} castShadow>
        <boxGeometry args={[0.14, 0.14, 0.14]} />
      </mesh>

      {/* intrusion sensor housings */}
      {[-0.7, 0.7].map((x, i) => (
        <mesh key={i} position={[x, 0.3, 0.15]} material={shellMat} castShadow>
          <boxGeometry args={[0.08, 0.08, 0.08]} />
        </mesh>
      ))}

      {/* mounting frame legs */}
      {[-0.5, 0.5].map((x, i) => (
        <mesh key={i} position={[x, -0.62, 0]} material={railMat} castShadow>
          <boxGeometry args={[0.08, 0.16, 0.5]} />
        </mesh>
      ))}

      <StatusLight position={[-0.55, 0.5, 0.2]} offset={0} />
      <StatusLight position={[0.55, 0.5, 0.2]} offset={0.7} />
    </group>
  );
}
