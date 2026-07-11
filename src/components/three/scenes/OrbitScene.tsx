"use client";

import { useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { EdgeBeam } from "@/components/three/EdgeBeam";
import { useIsMobile, particleCount, usePrefersReducedMotion } from "@/lib/performance";

interface OrbitSceneProps {
  progressRef?: MutableRefObject<number>;
}

const INNER_COUNT = 4;
const OUTER_COUNT = 6;
const DUMMY = new THREE.Object3D();

function ringPositions(count: number, radius: number, y: number) {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2;
    return new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius);
  });
}

export function OrbitScene({ progressRef }: OrbitSceneProps) {
  const group = useRef<THREE.Group>(null);
  const ring1 = useRef<THREE.Mesh>(null);
  const ring2 = useRef<THREE.Mesh>(null);
  const ring1Mat = useRef<any>(null);
  const ring2Mat = useRef<any>(null);
  const hubMat = useRef<any>(null);
  const containerMesh = useRef<THREE.InstancedMesh>(null);

  const isMobile = useIsMobile();
  const reducedMotion = usePrefersReducedMotion();
  const containerCount = particleCount(isMobile ? 10 : 18, isMobile, reducedMotion);

  const inner = useMemo(() => ringPositions(INNER_COUNT, 1.8, 0.2), []);
  const outer = useMemo(() => ringPositions(OUTER_COUNT, 3.2, -0.3), []);

  const containers = useMemo(
    () =>
      Array.from({ length: containerCount }, () => ({
        from: inner[Math.floor(Math.random() * inner.length)],
        to: outer[Math.floor(Math.random() * outer.length)],
        speed: 0.15 + Math.random() * 0.25,
        phase: Math.random(),
      })),
    [containerCount, inner, outer]
  );

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (group.current) group.current.rotation.y += delta * (0.04 + progress * 0.03);
    if (ring1.current) ring1.current.rotation.z += delta * 0.08;
    if (ring2.current) ring2.current.rotation.z -= delta * 0.05;

    if (ring1Mat.current) {
      ring1Mat.current.uTime = t;
      ring1Mat.current.uThreatLevel = progress * 0.4;
    }
    if (ring2Mat.current) {
      ring2Mat.current.uTime = t;
      ring2Mat.current.uThreatLevel = progress * 0.4;
    }
    if (hubMat.current) {
      hubMat.current.uTime = t;
      hubMat.current.uActivation = 0.5 + progress * 0.5;
    }

    if (containerMesh.current) {
      containers.forEach((container, index) => {
        const cycle = (t * container.speed + container.phase) % 1;
        const eased = THREE.MathUtils.smoothstep(cycle, 0, 1);
        DUMMY.position.lerpVectors(container.from, container.to, eased);
        DUMMY.position.y += Math.sin(cycle * Math.PI) * 0.4;
        DUMMY.scale.setScalar(0.12);
        DUMMY.rotation.set(t, t * 0.7, 0);
        DUMMY.updateMatrix();
        containerMesh.current!.setMatrixAt(index, DUMMY.matrix);
      });
      containerMesh.current.instanceMatrix.needsUpdate = true;
    }
  });

  return (
    <group ref={group}>
      <mesh>
        <sphereGeometry args={[0.5, 32, 32]} />
        <energyMaterial
          ref={hubMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#7A2200"
          uColorBright="#FF9A3D"
          uFresnelPower={1.3}
          uNoiseScale={1.6}
          uIntensity={1.3}
        />
      </mesh>

      {inner.map((pos, i) => (
        <mesh key={`inner-${i}`} position={pos}>
          <boxGeometry args={[0.24, 0.4, 0.24]} />
          <meshStandardMaterial color="#0d0d0d" metalness={0.8} roughness={0.25} emissive="#FF5A00" emissiveIntensity={0.5} />
        </mesh>
      ))}
      {outer.map((pos, i) => (
        <mesh key={`outer-${i}`} position={pos}>
          <boxGeometry args={[0.2, 0.32, 0.2]} />
          <meshStandardMaterial color="#0d0d0d" metalness={0.8} roughness={0.25} emissive="#C84400" emissiveIntensity={0.4} />
        </mesh>
      ))}

      {inner.map((pos, i) => (
        <EdgeBeam key={`hub-${i}`} from={new THREE.Vector3(0, 0, 0)} to={pos} width={0.02} color="#FF7A1A" />
      ))}
      {outer.map((pos, i) => (
        <EdgeBeam key={`route-${i}`} from={inner[i % inner.length]} to={pos} width={0.016} color="#C84400" speed={0.5} />
      ))}

      <instancedMesh ref={containerMesh} args={[undefined, undefined, containerCount]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color="#111" metalness={0.85} roughness={0.2} emissive="#FF9A3D" emissiveIntensity={0.9} />
      </instancedMesh>

      <mesh ref={ring1} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[3.7, 0.012, 8, 128]} />
        <scanMaterial ref={ring1Mat} transparent depthWrite={false} side={THREE.DoubleSide} uColor="#FF5A00" uDensity={60} uScanSpeed={0.2} />
      </mesh>
      <mesh ref={ring2} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[4.3, 0.01, 8, 128]} />
        <scanMaterial ref={ring2Mat} transparent depthWrite={false} side={THREE.DoubleSide} uColor="#FF7A1A" uDensity={80} uScanSpeed={-0.15} />
      </mesh>
    </group>
  );
}
