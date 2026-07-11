"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Sparkles } from "@react-three/drei";
import * as THREE from "three";
import ReactorMesh from "./models/ReactorMesh";
import { METAL } from "./materialHooks";

interface HeroReactorSceneProps {
  progressRef: React.MutableRefObject<number>;
  reducedMotion?: boolean;
}

const DOOR_COUNT = 9;
const REACTOR_SCALE = 0.62;
const DOOR_BASE_RADIUS = 2.6 * REACTOR_SCALE * 1.15;
const DOOR_OPEN_AMPLITUDE = DOOR_BASE_RADIUS * 0.35;
const DOOR_PANEL_SCALE = DOOR_BASE_RADIUS / 3.5;

export default function HeroReactorScene({ progressRef, reducedMotion = false }: HeroReactorSceneProps) {
  const reactorRef = useRef<THREE.Group>(null);
  const sceneRef = useRef<THREE.Group>(null);
  const doorRefs = useRef<(THREE.Group | null)[]>([]);
  const pointerTarget = useRef({ x: 0, y: 0 });

  const doors = useMemo(
    () =>
      new Array(DOOR_COUNT).fill(0).map((_, i) => {
        const angle = (i / DOOR_COUNT) * Math.PI * 2;
        return { angle, dir: i % 2 === 0 ? 1 : -1 };
      }),
    []
  );

  useFrame((state, delta) => {
    const progress = progressRef.current;

    if (sceneRef.current) {
      const targetX = reducedMotion ? 0 : state.pointer.x * 0.22;
      const targetY = reducedMotion ? 0 : state.pointer.y * 0.14;
      pointerTarget.current.x += (targetX - pointerTarget.current.x) * 0.04;
      pointerTarget.current.y += (targetY - pointerTarget.current.y) * 0.04;
      sceneRef.current.rotation.y = pointerTarget.current.x + progress * 0.6;
      sceneRef.current.rotation.x = -pointerTarget.current.y;
    }

    if (reactorRef.current) {
      const targetScale = REACTOR_SCALE * (1 + progress * 0.12);
      reactorRef.current.scale.setScalar(THREE.MathUtils.lerp(reactorRef.current.scale.x, targetScale, 0.08));
      reactorRef.current.rotation.z += delta * (0.03 + progress * 0.05);
    }

    doorRefs.current.forEach((door, i) => {
      if (!door) return;
      const { dir } = doors[i];
      const targetRotation = progress * dir * (Math.PI / 3.2);
      const targetOffset = progress * DOOR_OPEN_AMPLITUDE;
      door.rotation.y = THREE.MathUtils.lerp(door.rotation.y, targetRotation, 0.08);
      door.userData.offset = THREE.MathUtils.lerp(door.userData.offset ?? 0, targetOffset, 0.08);
      const angle = doors[i].angle;
      const r = DOOR_BASE_RADIUS + door.userData.offset;
      door.position.set(Math.cos(angle) * r, Math.sin(angle) * r, 0);
    });
  });

  return (
    <group ref={sceneRef}>
      <ambientLight intensity={0.15} color="#2a1810" />
      <directionalLight position={[4, 5, 4]} intensity={0.75} color="#FFA048" />
      <directionalLight position={[-4, -3, -2]} intensity={0.3} color="#C94700" />
      <pointLight position={[0, 0, 2]} color="#FF5A00" intensity={4} distance={10} decay={2} />

      <ReactorMesh ref={reactorRef} scale={REACTOR_SCALE} detail={1.4} />

      {doors.map((d, i) => (
        <group
          key={i}
          ref={(el) => {
            doorRefs.current[i] = el;
          }}
          position={[Math.cos(d.angle) * DOOR_BASE_RADIUS, Math.sin(d.angle) * DOOR_BASE_RADIUS, 0]}
        >
          <mesh rotation={[Math.PI / 2, 0, d.angle]} castShadow>
            <boxGeometry args={[0.5 * DOOR_PANEL_SCALE, 1.3 * DOOR_PANEL_SCALE, 0.22 * DOOR_PANEL_SCALE]} />
            <meshStandardMaterial {...METAL.black} />
          </mesh>
        </group>
      ))}

      {!reducedMotion && (
        <Sparkles count={60} scale={[5.5, 3.4, 3.4]} size={1.8} speed={0.25} color="#C94700" opacity={0.3} noise={1.2} />
      )}
    </group>
  );
}
