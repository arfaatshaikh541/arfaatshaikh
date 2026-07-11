"use client";

import { useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { usePointerParallax } from "@/components/three/usePointerParallax";
import { usePrefersReducedMotion } from "@/lib/performance";

interface ArchitectureSceneProps {
  progressRef?: MutableRefObject<number>;
}

const LAYER_COUNT = 6;

export function ArchitectureScene({ progressRef }: ArchitectureSceneProps) {
  const group = useRef<THREE.Group>(null);
  const layerRefs = useRef<(THREE.Mesh | null)[]>([]);
  const dashboardMat = useRef<any>(null);
  const coreMat = useRef<any>(null);
  const pointer = usePointerParallax();
  const reducedMotion = usePrefersReducedMotion();

  const layers = useMemo(
    () =>
      Array.from({ length: LAYER_COUNT }, (_, i) => ({
        target: new THREE.Vector3(0, i * 0.85 - 2.1, 0),
        dispersed: new THREE.Vector3(
          (Math.random() - 0.5) * 4.5,
          i * 0.85 - 2.1 + (Math.random() - 0.5) * 2,
          (Math.random() - 0.5) * 4.5
        ),
        width: 2.6 - i * 0.15,
      })),
    []
  );

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (group.current) {
      group.current.rotation.y += delta * 0.05;
      if (!reducedMotion) {
        group.current.rotation.y += pointer.current.x * 0.0015;
      }
    }

    layers.forEach((layer, index) => {
      const mesh = layerRefs.current[index];
      if (!mesh) return;
      const eased = THREE.MathUtils.smoothstep(progress, 0, 1);
      mesh.position.lerpVectors(layer.dispersed, layer.target, eased);
      mesh.rotation.y = (1 - eased) * (index % 2 === 0 ? 1 : -1) * 0.6;
      const material = mesh.material as THREE.MeshStandardMaterial;
      material.emissiveIntensity = 0.25 + eased * 0.7;
    });

    if (dashboardMat.current) {
      dashboardMat.current.uTime = t;
      dashboardMat.current.uThreatLevel = 0;
      dashboardMat.current.uScanSpeed = 0.15;
    }
    if (coreMat.current) {
      coreMat.current.uTime = t;
      coreMat.current.uActivation = 0.5 + progress * 0.5;
    }
  });

  return (
    <group ref={group}>
      {layers.map((layer, index) => (
        <mesh
          key={index}
          ref={(el) => {
            layerRefs.current[index] = el;
          }}
        >
          <boxGeometry args={[layer.width, 0.22, 1.5]} />
          <meshStandardMaterial
            color="#0d0d0d"
            metalness={0.75}
            roughness={0.3}
            emissive="#FF5A00"
            emissiveIntensity={0.3}
          />
        </mesh>
      ))}

      <mesh position={[0, LAYER_COUNT * 0.85 - 1.6, 0]} rotation={[-Math.PI / 2.4, 0, 0]}>
        <planeGeometry args={[2.4, 1.5, 1, 1]} />
        <scanMaterial ref={dashboardMat} transparent depthWrite={false} side={THREE.DoubleSide} uColor="#FF7A1A" uDensity={18} />
      </mesh>

      <mesh position={[0, -2.6, 0]}>
        <sphereGeometry args={[0.4, 32, 32]} />
        <energyMaterial
          ref={coreMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#7A2200"
          uColorBright="#FF9A3D"
          uFresnelPower={1.6}
          uNoiseScale={1.8}
          uIntensity={1.2}
        />
      </mesh>
    </group>
  );
}
