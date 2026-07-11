"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Billboard } from "@react-three/drei";
import * as THREE from "three";
import noiseGLSL from "@/shaders/noise.glsl";
import fireVertexGLSL from "@/shaders/fireVertex.glsl";
import fireFragmentGLSL from "@/shaders/fireFragment.glsl";
import { sceneState } from "@/lib/sceneStore";

const vertexShader = `${noiseGLSL}\n${fireVertexGLSL}`;
const fragmentShader = `${noiseGLSL}\n${fireFragmentGLSL}`;

const OPENING_DIRS = [
  new THREE.Vector3(0.9, 0.35, 0.2),
  new THREE.Vector3(-0.6, -0.4, 0.7),
  new THREE.Vector3(-0.2, 0.85, -0.5),
  new THREE.Vector3(0.3, -0.75, -0.6),
  new THREE.Vector3(-0.8, 0.15, -0.55),
].map((v) => v.normalize());

function FlameJet({ direction, seed }: { direction: THREE.Vector3; seed: number }) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const groupRef = useRef<THREE.Group>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: seed * 10 },
      uIntensity: { value: 0.1 },
      uSeed: { value: seed },
      uColorBase: { value: new THREE.Color("#8b0000") },
      uColorHot: { value: new THREE.Color("#ff3b20") },
    }),
    [seed]
  );

  useFrame((_, delta) => {
    const mat = materialRef.current;
    if (!mat) return;
    mat.uniforms.uTime.value += delta;
    const target = sceneState.flameIntensity * (0.7 + 0.3 * Math.sin(seed * 12.9));
    mat.uniforms.uIntensity.value = THREE.MathUtils.lerp(
      mat.uniforms.uIntensity.value,
      Math.max(0, target),
      0.08
    );
    if (groupRef.current) {
      const scale = 0.7 + sceneState.flameIntensity * 0.9;
      groupRef.current.scale.setScalar(scale);
    }
  });

  const position = direction.clone().multiplyScalar(1.62);

  return (
    <group ref={groupRef} position={position}>
      <Billboard>
        <mesh position={[0, 0.42, 0]}>
          <planeGeometry args={[0.75, 1.1, 1, 24]} />
          <shaderMaterial
            ref={materialRef}
            vertexShader={vertexShader}
            fragmentShader={fragmentShader}
            uniforms={uniforms}
            transparent
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      </Billboard>
    </group>
  );
}

export function Flames() {
  return (
    <>
      {OPENING_DIRS.map((direction, index) => (
        <FlameJet key={index} direction={direction} seed={(index + 1) / OPENING_DIRS.length} />
      ))}
    </>
  );
}
