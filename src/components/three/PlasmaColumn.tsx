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

export function PlasmaColumn() {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const groupRef = useRef<THREE.Group>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uIntensity: { value: 0 },
      uSeed: { value: 0.42 },
      uColorBase: { value: new THREE.Color("#8b0000") },
      uColorHot: { value: new THREE.Color("#ff3b20") },
    }),
    []
  );

  useFrame((_, delta) => {
    const mat = materialRef.current;
    const group = groupRef.current;
    if (!mat || !group) return;
    mat.uniforms.uTime.value += delta;
    const target = sceneState.splitAmount;
    mat.uniforms.uIntensity.value = THREE.MathUtils.lerp(
      mat.uniforms.uIntensity.value,
      target,
      0.06
    );
    group.scale.x = THREE.MathUtils.lerp(group.scale.x, 0.5 + target * 0.9, 0.06);
    group.visible = target > 0.02;
  });

  return (
    <group ref={groupRef} scale={[0.5, 1, 1]}>
      <Billboard>
        <mesh rotation={[0, 0, Math.PI]}>
          <planeGeometry args={[1.1, 4.2, 1, 32]} />
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
