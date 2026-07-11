"use client";

import { useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { EdgeBeam } from "@/components/three/EdgeBeam";
import { useIsMobile, particleCount, usePrefersReducedMotion } from "@/lib/performance";

interface AssemblySceneProps {
  progressRef?: MutableRefObject<number>;
}

const RAILS = 4;
const RAIL_SPAN = 5.6;
const DUMMY = new THREE.Object3D();

export function AssemblyScene({ progressRef }: AssemblySceneProps) {
  const group = useRef<THREE.Group>(null);
  const packagesRef = useRef<THREE.InstancedMesh>(null);
  const armRef = useRef<THREE.Group>(null);
  const gateRefs = useRef<(THREE.Mesh | null)[]>([]);

  const isMobile = useIsMobile();
  const reducedMotion = usePrefersReducedMotion();
  const packageCount = particleCount(isMobile ? 12 : 20, isMobile, reducedMotion);

  const packages = useMemo(
    () =>
      Array.from({ length: packageCount }, (_, i) => ({
        lane: i % RAILS,
        offset: Math.random() * RAIL_SPAN,
        speed: 0.5 + Math.random() * 0.4,
      })),
    [packageCount]
  );

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (group.current) group.current.rotation.y = -0.35 + progress * 0.25;

    if (armRef.current) {
      armRef.current.rotation.z = Math.sin(t * 1.4) * 0.35;
      armRef.current.rotation.x = Math.cos(t * 0.9) * 0.12;
    }

    gateRefs.current.forEach((gate, i) => {
      if (!gate) return;
      gate.rotation.z += delta * (0.5 + i * 0.15);
    });

    if (packagesRef.current) {
      packages.forEach((pkg, index) => {
        const laneY = pkg.lane * 0.9 - (RAILS - 1) * 0.45;
        const x = (((t * (0.7 + pkg.speed * progress * 1.5 + 0.3) + pkg.offset) % RAIL_SPAN) - RAIL_SPAN / 2);
        DUMMY.position.set(x, laneY, Math.sin(x * 1.5 + pkg.lane) * 0.15);
        DUMMY.rotation.set(0, x * 0.8, 0);
        DUMMY.scale.setScalar(0.22);
        DUMMY.updateMatrix();
        packagesRef.current!.setMatrixAt(index, DUMMY.matrix);
      });
      packagesRef.current.instanceMatrix.needsUpdate = true;
    }
  });

  return (
    <group ref={group}>
      {Array.from({ length: RAILS }).map((_, lane) => {
        const y = lane * 0.9 - (RAILS - 1) * 0.45;
        return (
          <EdgeBeam
            key={lane}
            from={new THREE.Vector3(-RAIL_SPAN / 2, y, 0)}
            to={new THREE.Vector3(RAIL_SPAN / 2, y, 0)}
            width={0.04}
            speed={0.9}
            color={lane === RAILS - 1 ? "#FF9A3D" : "#C84400"}
          />
        );
      })}

      <instancedMesh ref={packagesRef} args={[undefined, undefined, packageCount]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial
          color="#0b0b0b"
          metalness={0.8}
          roughness={0.25}
          emissive="#FF5A00"
          emissiveIntensity={0.9}
        />
      </instancedMesh>

      {[-1.8, 0, 1.8].map((x, i) => (
        <mesh
          key={x}
          position={[x, -(RAILS - 1) * 0.45 - 0.6, 0]}
          rotation={[Math.PI / 2, 0, 0]}
          ref={(el) => {
            gateRefs.current[i] = el;
          }}
        >
          <torusGeometry args={[0.4, 0.03, 12, 48]} />
          <meshStandardMaterial color="#111" metalness={0.9} roughness={0.2} emissive="#FF7A1A" emissiveIntensity={0.6} />
        </mesh>
      ))}

      <group ref={armRef} position={[0, 1.4, 0]}>
        <mesh position={[0, -0.5, 0]}>
          <cylinderGeometry args={[0.05, 0.05, 1, 8]} />
          <meshStandardMaterial color="#111" metalness={0.85} roughness={0.3} />
        </mesh>
        <mesh position={[0, -1, 0]}>
          <boxGeometry args={[0.5, 0.12, 0.12]} />
          <meshStandardMaterial color="#0b0b0b" metalness={0.9} roughness={0.2} emissive="#FF5A00" emissiveIntensity={0.4} />
        </mesh>
      </group>
    </group>
  );
}
