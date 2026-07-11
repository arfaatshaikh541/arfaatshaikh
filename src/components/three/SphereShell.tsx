"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import noiseGLSL from "@/shaders/noise.glsl";
import shellVertexGLSL from "@/shaders/shellVertex.glsl";
import shellFragmentGLSL from "@/shaders/shellFragment.glsl";
import { sceneState } from "@/lib/sceneStore";

const vertexShader = `${noiseGLSL}\n${shellVertexGLSL}`;
const fragmentShader = `${noiseGLSL}\n${shellFragmentGLSL}`;

interface SphereShellProps {
  radius: number;
  openAmountMultiplier: number;
  dimmed?: boolean;
}

export function SphereShell({ radius, openAmountMultiplier, dimmed = false }: SphereShellProps) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uOpenAmount: { value: 0.04 },
      uSeparation: { value: 0 },
      uSplit: { value: 0 },
      uBrightness: { value: 0.3 },
      uLightDir: { value: new THREE.Vector3(0.4, 0.8, 0.6) },
      uRimColor: {
        value: new THREE.Color(dimmed ? "#4a0000" : "#ff1a12"),
      },
    }),
    [dimmed]
  );

  useFrame((_, delta) => {
    const mat = materialRef.current;
    if (!mat) return;
    mat.uniforms.uTime.value += delta;
    mat.uniforms.uOpenAmount.value = THREE.MathUtils.lerp(
      mat.uniforms.uOpenAmount.value,
      sceneState.shellOpen * openAmountMultiplier,
      0.06
    );
    mat.uniforms.uSeparation.value = THREE.MathUtils.lerp(
      mat.uniforms.uSeparation.value,
      sceneState.separation,
      0.06
    );
    mat.uniforms.uBrightness.value = THREE.MathUtils.lerp(
      mat.uniforms.uBrightness.value,
      sceneState.coreBrightness,
      0.06
    );
    mat.uniforms.uSplit.value = THREE.MathUtils.lerp(
      mat.uniforms.uSplit.value,
      sceneState.splitAmount,
      0.06
    );
  });

  return (
    <mesh renderOrder={1}>
      <sphereGeometry args={[radius, 160, 160]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        side={THREE.FrontSide}
      />
    </mesh>
  );
}
