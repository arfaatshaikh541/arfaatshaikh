"use client";

import { useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { EdgeBeam } from "@/components/three/EdgeBeam";
import { usePointerParallax } from "@/components/three/usePointerParallax";
import { usePrefersReducedMotion } from "@/lib/performance";

interface CommandSceneProps {
  progressRef?: MutableRefObject<number>;
}

const MODULE_COUNT = 9;

function fibonacciSphere(count: number, radius: number) {
  const points: THREE.Vector3[] = [];
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i += 1) {
    const y = 1 - (i / (count - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = goldenAngle * i;
    points.push(new THREE.Vector3(Math.cos(theta) * r * radius, y * radius, Math.sin(theta) * r * radius));
  }
  return points;
}

export function CommandScene({ progressRef }: CommandSceneProps) {
  const group = useRef<THREE.Group>(null);
  const coreMat = useRef<any>(null);
  const moduleRefs = useRef<(THREE.Mesh | null)[]>([]);
  const pointer = usePointerParallax();
  const reducedMotion = usePrefersReducedMotion();

  const modules = useMemo(() => {
    const targets = fibonacciSphere(MODULE_COUNT, 2.4);
    return targets.map((target) => ({
      target,
      dispersed: target.clone().multiplyScalar(2.4 + Math.random() * 1.6),
    }));
  }, []);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (group.current) {
      group.current.rotation.y += delta * 0.05;
      if (!reducedMotion) {
        group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, pointer.current.y * 0.1, 0.03);
      }
    }

    if (coreMat.current) {
      coreMat.current.uTime = t;
      coreMat.current.uActivation = 0.6 + progress * 0.4;
    }

    modules.forEach((module, index) => {
      const mesh = moduleRefs.current[index];
      if (!mesh) return;
      const eased = THREE.MathUtils.smoothstep(progress, 0, 1);
      mesh.position.lerpVectors(module.dispersed, module.target, eased);
      mesh.rotation.y = t * 0.4 + index;
      const material = mesh.material as THREE.MeshStandardMaterial;
      material.emissiveIntensity = 0.35 + eased * 0.75;
    });
  });

  return (
    <group ref={group}>
      <mesh>
        <icosahedronGeometry args={[0.9, 2]} />
        <energyMaterial
          ref={coreMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#7A2200"
          uColorBright="#FF9A3D"
          uFresnelPower={1.1}
          uNoiseScale={1.8}
          uIntensity={1.5}
        />
      </mesh>

      {modules.map((module, index) => (
        <group key={index}>
          <mesh
            position={module.dispersed}
            ref={(el) => {
              moduleRefs.current[index] = el;
            }}
          >
            <boxGeometry args={[0.32, 0.32, 0.32]} />
            <meshStandardMaterial color="#0d0d0d" metalness={0.85} roughness={0.2} emissive="#FF5A00" emissiveIntensity={0.35} />
          </mesh>
          <EdgeBeam from={new THREE.Vector3(0, 0, 0)} to={module.target} width={0.014} color="#C84400" speed={0.35} />
        </group>
      ))}
    </group>
  );
}
