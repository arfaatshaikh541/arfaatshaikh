"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

// A glowing platform beneath the hero object — concentric rings, a ring of
// tick marks, and a beam of light connecting the object to the ground — all
// procedural (no textures), reusing the same additive-red language as the
// rest of the hero (ElectricArcs, OrbitRings). Sits at a fixed
// offset below the model rather than as a child of CoreModel's own scaled
// group, since it needs to stay grounded regardless of the model's swell/
// heartbeat scale animation.
const PLATFORM_Y = -2.35;

function FlatRing({
  radius,
  thickness,
  speed,
  opacity,
}: {
  radius: number;
  thickness: number;
  speed: number;
  opacity: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame((state, delta) => {
    if (ref.current) ref.current.rotation.z += delta * speed;
    if (materialRef.current) {
      const heat = 0.35 + sceneState.coreBrightness * 0.4 + sceneState.hoverIntensity * 0.4 + sceneState.pulseStrength * 0.8;
      const flicker = 0.9 + Math.sin(state.clock.elapsedTime * 3 + radius * 5) * 0.1;
      materialRef.current.opacity = THREE.MathUtils.lerp(
        materialRef.current.opacity,
        opacity * heat * flicker,
        0.1
      );
    }
  });

  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[radius - thickness, radius, 64]} />
      <meshBasicMaterial
        ref={materialRef}
        color="#ff2a1a"
        transparent
        opacity={opacity}
        side={THREE.DoubleSide}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
}

function TickMarks({ radius, count }: { radius: number; count: number }) {
  const groupRef = useRef<THREE.Group>(null);
  const materialRefs = useRef<THREE.MeshBasicMaterial[]>([]);

  const ticks = useMemo(
    () => Array.from({ length: count }, (_, i) => (i / count) * Math.PI * 2),
    [count]
  );

  useFrame((state) => {
    if (groupRef.current) groupRef.current.rotation.y = state.clock.elapsedTime * 0.04;
    const heat = 0.4 + sceneState.coreBrightness * 0.5 + sceneState.pulseStrength * 0.9;
    materialRefs.current.forEach((mat) => {
      if (mat) mat.opacity = THREE.MathUtils.lerp(mat.opacity, heat, 0.1);
    });
  });

  return (
    <group ref={groupRef}>
      {ticks.map((angle, i) => (
        <mesh
          key={i}
          position={[Math.cos(angle) * radius, 0, Math.sin(angle) * radius]}
          rotation={[-Math.PI / 2, 0, -angle]}
        >
          <planeGeometry args={[0.04, 0.16]} />
          <meshBasicMaterial
            ref={(m) => {
              if (m) materialRefs.current[i] = m;
            }}
            color="#ff5a2e"
            transparent
            opacity={0.6}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}
    </group>
  );
}

// A cone whose sharp point touches the platform and widens going back up
// toward the model, like a beam draining down to a single point of contact.
// THREE's ConeGeometry puts its apex at local +height/2 by default; flipping
// 180° and re-centering moves that apex down to local y=0 (the platform)
// with the wide base sitting up near the model instead.
const BEAM_HEIGHT = Math.abs(PLATFORM_Y);

function Beam() {
  const materialRef = useRef<THREE.MeshBasicMaterial>(null);
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame(() => {
    const heat = 0.3 + sceneState.coreBrightness * 0.35 + sceneState.hoverIntensity * 0.4 + sceneState.pulseStrength * 1.0;
    if (materialRef.current) {
      materialRef.current.opacity = THREE.MathUtils.lerp(materialRef.current.opacity, heat, 0.08);
    }
    if (meshRef.current) {
      const scaleXZ = 1 + sceneState.pulseStrength * 0.5;
      meshRef.current.scale.x = THREE.MathUtils.lerp(meshRef.current.scale.x, scaleXZ, 0.1);
      meshRef.current.scale.z = meshRef.current.scale.x;
    }
  });

  return (
    <mesh ref={meshRef} position={[0, BEAM_HEIGHT / 2, 0]} rotation={[Math.PI, 0, 0]}>
      <coneGeometry args={[0.16, BEAM_HEIGHT, 16, 1, true]} />
      <meshBasicMaterial
        ref={materialRef}
        color="#ff3b20"
        transparent
        opacity={0.3}
        side={THREE.DoubleSide}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
}

export function Pedestal() {
  return (
    <group position={[0, PLATFORM_Y, 0]}>
      <FlatRing radius={0.55} thickness={0.012} speed={0.12} opacity={0.9} />
      <FlatRing radius={0.85} thickness={0.008} speed={-0.08} opacity={0.55} />
      <FlatRing radius={1.25} thickness={0.02} speed={0.05} opacity={0.4} />
      <FlatRing radius={1.7} thickness={0.006} speed={-0.03} opacity={0.28} />
      <TickMarks radius={1.7} count={28} />
      <Beam />
    </group>
  );
}
