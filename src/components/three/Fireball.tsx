"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import noiseGLSL from "@/shaders/noise.glsl";

const vertexShader = `
  varying vec3 vNormal;
  varying vec3 vLocalPos;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vLocalPos = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = `
  ${noiseGLSL}
  uniform float uTime;
  uniform float uIntensity;
  varying vec3 vNormal;
  varying vec3 vLocalPos;

  void main() {
    // A roiling surface: fast-flowing turbulence layered with a slower
    // drift, sampled in the ball's own local space so it reads as real
    // volume churning rather than a texture sliding across a sphere.
    float churn = fbm(vLocalPos * 3.2 + vec3(0.0, -uTime * 1.6, 0.0), 4);
    float licks = fbm(vLocalPos * 6.5 + vec3(uTime * 0.9, -uTime * 2.4, uTime * 0.6), 3);
    float heat = clamp(0.45 + churn * 0.4 + licks * 0.3, 0.0, 1.0);

    // Fresnel-style rim: the ball reads brightest/hottest dead-center-on
    // and cools toward the silhouette edge, like looking into a furnace
    // rather than a flat-lit sphere.
    float rim = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 1.6);
    float core = 1.0 - rim;

    vec3 dark = vec3(0.55, 0.05, 0.0);
    vec3 mid = vec3(1.0, 0.35, 0.05);
    vec3 hot = vec3(1.0, 0.85, 0.45);
    vec3 color = mix(dark, mid, heat);
    color = mix(color, hot, pow(heat, 3.0) * core);

    float alpha = (0.35 + heat * 0.5) * (0.5 + core * 0.6) * uIntensity;
    gl_FragColor = vec4(color, clamp(alpha, 0.0, 1.0));
  }
`;

/**
 * A genuine roiling fireball (procedural 3D noise driving both color and
 * shape-reading brightness, not a flat glow sphere) sitting inside the
 * core mesh — visible mainly through the gap the wings open under
 * hover/click/scroll. Intensity rides the same heartbeat math CoreModel
 * already drives the crack shader with, passed in as a prop so both stay
 * in lockstep without duplicating the calculation.
 */
export function Fireball({
  position,
  radius,
  intensityRef,
}: {
  position: THREE.Vector3;
  radius: number;
  intensityRef: React.RefObject<number>;
}) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uIntensity: { value: 0 },
    }),
    []
  );

  useFrame((state, delta) => {
    const mat = materialRef.current;
    if (!mat) return;
    mat.uniforms.uTime.value += delta;
    mat.uniforms.uIntensity.value = THREE.MathUtils.lerp(
      mat.uniforms.uIntensity.value,
      intensityRef.current ?? 0,
      0.15
    );
  });

  return (
    <mesh position={position} scale={radius * 0.62}>
      <sphereGeometry args={[1, 32, 32]} />
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
  );
}
