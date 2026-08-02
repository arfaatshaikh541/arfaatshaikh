"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import noiseGLSL from "@/shaders/noise.glsl";
import fireCoreVertexGLSL from "@/shaders/fireCoreVertex.glsl";
import fireCoreFragmentGLSL from "@/shaders/fireCoreFragment.glsl";
import { sceneState } from "@/lib/sceneStore";

const vertexShader = `${noiseGLSL}\n${fireCoreVertexGLSL}`;
const fragmentShader = `${noiseGLSL}\n${fireCoreFragmentGLSL}`;

// Sits inside CoreModel's own recentered/scaled group, so its position and
// scale are expressed in that same local mesh space — the model's local
// bounding box half-extents are roughly 0.204/0.219/0.102 (X/Y/Z). This
// needs to stay well inside that, not merely inset from it: the shell's
// own thickness plus the blurred alpha cutout edges mean anything close to
// the full half-extent pokes through the surface and reads as its own
// separate blob rather than a glow seen through gaps. ~30% of the shell's
// size keeps it a genuinely contained core.
const CORE_SCALE: [number, number, number] = [0.06, 0.07, 0.032];

export function FireCore() {
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uBrightness: { value: 0.5 },
      uTurbulence: { value: 0.2 },
      uColorEdge: { value: new THREE.Color("#3a0400") },
      uColorMid: { value: new THREE.Color("#ff5a1a") },
      uColorCore: { value: new THREE.Color("#ffd166") },
    }),
    []
  );

  useFrame((_, delta) => {
    const mat = materialRef.current;
    if (!mat) return;
    mat.uniforms.uTime.value += delta;

    const targetBrightness =
      0.45 +
      sceneState.coreBrightness * 0.5 +
      sceneState.hoverIntensity * 0.6 +
      sceneState.pulseStrength * 1.2;
    mat.uniforms.uBrightness.value = THREE.MathUtils.lerp(
      mat.uniforms.uBrightness.value,
      targetBrightness,
      0.08
    );

    const targetTurbulence =
      sceneState.turbulence + sceneState.hoverIntensity * 0.35 + sceneState.pulseStrength * 0.7;
    mat.uniforms.uTurbulence.value = THREE.MathUtils.lerp(
      mat.uniforms.uTurbulence.value,
      targetTurbulence,
      0.08
    );
  });

  return (
    <mesh scale={CORE_SCALE} renderOrder={-1}>
      <sphereGeometry args={[1, 64, 64]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
      />
    </mesh>
  );
}
