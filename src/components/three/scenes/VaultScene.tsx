"use client";

import { useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { useIsMobile, particleCount, usePrefersReducedMotion } from "@/lib/performance";

interface VaultSceneProps {
  progressRef?: MutableRefObject<number>;
}

const DUMMY = new THREE.Object3D();
const RING_RADII = [1.4, 1.9, 2.5];

export function VaultScene({ progressRef }: VaultSceneProps) {
  const group = useRef<THREE.Group>(null);
  const shellRef = useRef<THREE.Mesh>(null);
  const shellMat = useRef<any>(null);
  const coreMat = useRef<any>(null);
  const ringRefs = useRef<(THREE.Mesh | null)[]>([]);
  const ringMats = useRef<any[]>([]);
  const threatMesh = useRef<THREE.InstancedMesh>(null);

  const isMobile = useIsMobile();
  const reducedMotion = usePrefersReducedMotion();
  const threatCount = particleCount(isMobile ? 20 : 34, isMobile, reducedMotion);

  const threats = useMemo(
    () =>
      Array.from({ length: threatCount }, () => ({
        theta: Math.random() * Math.PI * 2,
        phi: Math.acos(2 * Math.random() - 1),
        speed: 0.15 + Math.random() * 0.2,
        phase: Math.random(),
      })),
    [threatCount]
  );

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;
    const barrierRadius = 3.1 - progress * 1.7;

    if (group.current) group.current.rotation.y += delta * 0.03;

    if (shellRef.current) shellRef.current.scale.setScalar(1 - progress * 0.12);
    if (shellMat.current) {
      shellMat.current.uTime = t;
      shellMat.current.uActivation = 0.5 + progress * 0.5;
    }
    if (coreMat.current) {
      coreMat.current.uTime = t;
      coreMat.current.uActivation = 0.6 + progress * 0.4;
    }

    ringRefs.current.forEach((ring, i) => {
      if (!ring) return;
      ring.rotation.z += delta * (0.25 + i * 0.18) * (i % 2 === 0 ? 1 : -1);
      ring.scale.setScalar(1 - progress * 0.15);
    });
    ringMats.current.forEach((mat) => {
      if (!mat) return;
      mat.uTime = t;
      mat.uThreatLevel = progress;
    });

    if (threatMesh.current) {
      threats.forEach((threat, index) => {
        const cycle = (t * threat.speed + threat.phase) % 1;
        const radius = barrierRadius + (6.5 - barrierRadius) * (1 - cycle);
        const x = radius * Math.sin(threat.phi) * Math.cos(threat.theta + t * 0.05);
        const y = radius * Math.sin(threat.phi) * Math.sin(threat.theta + t * 0.05) * 0.6;
        const z = radius * Math.cos(threat.phi);
        DUMMY.position.set(x, y, z);
        const scale = cycle < 0.05 ? 0.14 * (1 - progress * 0.6) : 0.14;
        DUMMY.scale.setScalar(scale);
        DUMMY.rotation.set(t + index, t * 0.6, 0);
        DUMMY.updateMatrix();
        threatMesh.current!.setMatrixAt(index, DUMMY.matrix);
      });
      threatMesh.current.instanceMatrix.needsUpdate = true;
    }
  });

  return (
    <group ref={group}>
      <mesh ref={shellRef}>
        <icosahedronGeometry args={[1.0, 2]} />
        <energyMaterial
          ref={shellMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#7A2200"
          uColorBright="#FF7A1A"
          uFresnelPower={2.2}
          uNoiseScale={1.0}
          uIntensity={0.9}
          wireframe
        />
      </mesh>

      <mesh>
        <sphereGeometry args={[0.5, 32, 32]} />
        <energyMaterial
          ref={coreMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#FF5A00"
          uColorBright="#FF9A3D"
          uFresnelPower={1.0}
          uNoiseScale={2.0}
          uIntensity={1.4}
        />
      </mesh>

      {RING_RADII.map((radius, i) => (
        <mesh
          key={radius}
          rotation={[Math.PI / 2 + i * 0.3, i * 0.4, 0]}
          ref={(el) => {
            ringRefs.current[i] = el;
          }}
        >
          <torusGeometry args={[radius, 0.02, 8, 96]} />
          <scanMaterial
            ref={(el: any) => {
              ringMats.current[i] = el;
            }}
            transparent
            depthWrite={false}
            side={THREE.DoubleSide}
            uColor="#FF5A00"
            uDensity={40}
            uScanSpeed={0.3 + i * 0.1}
          />
        </mesh>
      ))}

      <instancedMesh ref={threatMesh} args={[undefined, undefined, threatCount]}>
        <tetrahedronGeometry args={[1, 0]} />
        <meshStandardMaterial color="#1a0a05" metalness={0.5} roughness={0.5} emissive="#C84400" emissiveIntensity={0.8} />
      </instancedMesh>
    </group>
  );
}
