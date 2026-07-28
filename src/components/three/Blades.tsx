"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

interface BladeConfig {
  azimuth: number;
  elevation: number;
  roll: number;
  curlSign: number;
  parallaxPhase: number;
}

// Four asymmetric claw-like blades wrapping the core at varied angles,
// deliberately not evenly spaced — matches the reference mark rather than a
// tidy geometric ring.
const BLADE_CONFIGS: BladeConfig[] = [
  { azimuth: 0.35, elevation: 0.55, roll: 0.35, curlSign: 1, parallaxPhase: 1 },
  { azimuth: 2.55, elevation: -0.3, roll: -0.5, curlSign: -1, parallaxPhase: -0.7 },
  { azimuth: -2.35, elevation: 0.12, roll: 1.1, curlSign: 1, parallaxPhase: 0.5 },
  { azimuth: -0.85, elevation: -0.6, roll: -0.85, curlSign: -1, parallaxPhase: -1 },
];

const UP = new THREE.Vector3(0, 1, 0);
const X_AXIS = new THREE.Vector3(1, 0, 0);
const Z_AXIS = new THREE.Vector3(0, 0, 1);

// Scratch objects reused across all blades each frame to avoid per-frame
// allocation — safe since each blade's useFrame fully consumes them
// synchronously before the next one runs.
const scratchDynamic = new THREE.Quaternion();
const scratchExtra = new THREE.Quaternion();

function createBladeGeometry(): THREE.ExtrudeGeometry {
  // An asymmetric, scythe-like claw: narrow base, wide belly, sharp tip.
  const shape = new THREE.Shape();
  shape.moveTo(0, 0);
  shape.bezierCurveTo(0.34, 0.08, 0.5, 0.4, 0.34, 0.9);
  shape.bezierCurveTo(0.24, 1.3, 0.09, 1.75, 0, 2.1);
  shape.bezierCurveTo(-0.16, 1.75, -0.34, 1.25, -0.38, 0.8);
  shape.bezierCurveTo(-0.42, 0.38, -0.22, 0.08, 0, 0);

  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: 0.16,
    bevelEnabled: true,
    bevelThickness: 0.04,
    bevelSize: 0.035,
    bevelSegments: 3,
    curveSegments: 14,
  });
  geometry.translate(0, 0, -0.08);
  geometry.computeVertexNormals();
  return geometry;
}

interface BladeProps {
  config: BladeConfig;
  index: number;
  geometry: THREE.ExtrudeGeometry;
  metalMaterial: THREE.MeshStandardMaterial;
  glowMaterial: THREE.MeshBasicMaterial;
}

function Blade({ config, index, geometry, metalMaterial, glowMaterial }: BladeProps) {
  const groupRef = useRef<THREE.Group>(null);

  const dir = useMemo(
    () =>
      new THREE.Vector3(
        Math.cos(config.elevation) * Math.cos(config.azimuth),
        Math.sin(config.elevation),
        Math.cos(config.elevation) * Math.sin(config.azimuth)
      ).normalize(),
    [config]
  );

  const baseQuat = useMemo(() => {
    const align = new THREE.Quaternion().setFromUnitVectors(UP, dir);
    const roll = new THREE.Quaternion().setFromAxisAngle(dir, config.roll);
    return roll.multiply(align);
  }, [dir, config.roll]);

  useFrame((state) => {
    const group = groupRef.current;
    if (!group) return;

    const t = state.clock.elapsedTime;
    const open = sceneState.bladeOpen;
    const pulse = sceneState.pulseStrength;

    const radius = THREE.MathUtils.lerp(1.95, 2.75, open) + pulse * 0.3;
    group.position.copy(dir).multiplyScalar(radius);

    const curl = THREE.MathUtils.lerp(0.95, 0.12, open) * config.curlSign;
    const breathe = Math.sin(t * 0.5 + index * 1.6) * 0.025;
    const parallax =
      (sceneState.parallaxX * 0.12 + sceneState.parallaxY * 0.08) * config.parallaxPhase;

    scratchDynamic.setFromAxisAngle(X_AXIS, curl + breathe);
    scratchExtra.setFromAxisAngle(Z_AXIS, parallax + pulse * 0.15 * config.curlSign);
    scratchDynamic.multiply(scratchExtra);

    group.quaternion.copy(baseQuat).multiply(scratchDynamic);

    const scale = 1 + pulse * 0.08;
    group.scale.setScalar(scale);
  });

  return (
    <group ref={groupRef}>
      <mesh geometry={geometry} material={metalMaterial} />
      <mesh geometry={geometry} material={glowMaterial} scale={1.06} />
    </group>
  );
}

export function Blades() {
  const geometry = useMemo(() => createBladeGeometry(), []);

  const metalMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#050506",
        metalness: 0.95,
        roughness: 0.14,
        emissive: new THREE.Color("#4a0000"),
        emissiveIntensity: 0.12,
        flatShading: true,
      }),
    []
  );

  const glowMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: "#ff1a12",
        transparent: true,
        opacity: 0.1,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    []
  );

  useEffect(() => {
    return () => {
      geometry.dispose();
      metalMaterial.dispose();
      glowMaterial.dispose();
    };
  }, [geometry, metalMaterial, glowMaterial]);

  useFrame(() => {
    const heat = sceneState.coreBrightness * 0.2 + sceneState.hoverIntensity * 0.6 + sceneState.pulseStrength * 1.3;
    metalMaterial.emissiveIntensity = THREE.MathUtils.lerp(
      metalMaterial.emissiveIntensity,
      0.08 + heat,
      0.08
    );
    glowMaterial.opacity = THREE.MathUtils.lerp(
      glowMaterial.opacity,
      0.06 + sceneState.hoverIntensity * 0.4 + sceneState.pulseStrength * 0.45,
      0.08
    );
  });

  return (
    <>
      {BLADE_CONFIGS.map((config, i) => (
        <Blade
          key={i}
          config={config}
          index={i}
          geometry={geometry}
          metalMaterial={metalMaterial}
          glowMaterial={glowMaterial}
        />
      ))}
    </>
  );
}
