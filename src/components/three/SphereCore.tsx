"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import noiseGLSL from "@/shaders/noise.glsl";
import coreVertexGLSL from "@/shaders/coreVertex.glsl";
import coreFragmentGLSL from "@/shaders/coreFragment.glsl";
import { sceneState } from "@/lib/sceneStore";

const vertexShader = `${noiseGLSL}\n${coreVertexGLSL}`;
const fragmentShader = `${noiseGLSL}\n${coreFragmentGLSL}`;

export function SphereCore() {
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uBrightness: { value: 0.35 },
      uTurbulence: { value: 0.15 },
      uSplit: { value: 0 },
      uColorDeep: { value: new THREE.Color("#2a0000") },
      uColorHot: { value: new THREE.Color("#ff3b20") },
    }),
    []
  );

  useFrame((_, delta) => {
    const mat = materialRef.current;
    if (!mat) return;
    mat.uniforms.uTime.value += delta;
    mat.uniforms.uBrightness.value = THREE.MathUtils.lerp(
      mat.uniforms.uBrightness.value,
      sceneState.coreBrightness,
      0.06
    );
    mat.uniforms.uTurbulence.value = THREE.MathUtils.lerp(
      mat.uniforms.uTurbulence.value,
      sceneState.turbulence,
      0.06
    );
    mat.uniforms.uSplit.value = THREE.MathUtils.lerp(
      mat.uniforms.uSplit.value,
      sceneState.splitAmount,
      0.06
    );
  });

  return (
    <mesh renderOrder={0}>
      <sphereGeometry args={[1.32, 128, 128]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
      />
    </mesh>
  );
}
