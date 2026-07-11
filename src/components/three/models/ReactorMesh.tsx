"use client";

import { forwardRef, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useEnergySeamMaterial, useCoreGlowMaterial, METAL } from "../materialHooks";

interface ReactorMeshProps {
  scale?: number;
  detail?: number;
}

const ReactorMesh = forwardRef<THREE.Group, ReactorMeshProps>(function ReactorMesh(
  { scale = 1, detail = 1 },
  forwardedRef
) {
  const outerRef = useRef<THREE.Group>(null);
  const innerRef = useRef<THREE.Group>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const seamMat = useEnergySeamMaterial(20, 1.3);
  const coreMat = useCoreGlowMaterial("#FF5A00", 1.8);

  const plates = useMemo(() => {
    const count = Math.max(4, Math.round(14 * detail));
    return new Array(count).fill(0).map((_, i) => {
      const angle = (i / count) * Math.PI * 2;
      return { angle, radius: 2.15 };
    });
  }, [detail]);

  const outerSegments = useMemo(() => {
    const count = 24;
    return new Array(count).fill(0).map((_, i) => (i / count) * Math.PI * 2);
  }, []);

  useFrame((state, delta) => {
    if (outerRef.current) outerRef.current.rotation.z += delta * 0.06;
    if (innerRef.current) innerRef.current.rotation.z -= delta * 0.11;
    if (coreRef.current) {
      const t = state.clock.elapsedTime;
      coreRef.current.scale.setScalar(1 + Math.sin(t * 1.6) * 0.04);
    }
  });

  return (
    <group ref={forwardedRef} scale={scale}>
      {/* outer armored shell */}
      <group ref={outerRef}>
        <mesh castShadow receiveShadow>
          <torusGeometry args={[2.6, 0.16, 12, 64]} />
          <meshStandardMaterial {...METAL.black} />
        </mesh>
        {plates.map((p, i) => (
          <mesh
            key={i}
            position={[Math.cos(p.angle) * p.radius, Math.sin(p.angle) * p.radius, 0]}
            rotation={[0, 0, p.angle]}
            castShadow
          >
            <boxGeometry args={[0.32, 0.5, 0.14]} />
            <meshStandardMaterial {...METAL.gunmetal} />
          </mesh>
        ))}
        <mesh>
          <torusGeometry args={[2.32, 0.03, 8, 64]} />
          <primitive object={seamMat} attach="material" />
        </mesh>
      </group>

      {/* mid ring, static-ish */}
      <mesh castShadow receiveShadow>
        <torusGeometry args={[1.85, 0.2, 12, 56]} />
        <meshStandardMaterial {...METAL.graphite} />
      </mesh>
      {outerSegments.map((a, i) => (
        <mesh key={i} position={[Math.cos(a) * 1.85, Math.sin(a) * 1.85, 0.12]} rotation={[0, 0, a]}>
          <boxGeometry args={[0.06, 0.06, 0.22]} />
          <meshStandardMaterial color="#FF7A1A" emissive="#FF5A00" emissiveIntensity={i % 3 === 0 ? 1.4 : 0.2} />
        </mesh>
      ))}

      {/* inner rotating ring */}
      <group ref={innerRef}>
        <mesh castShadow receiveShadow>
          <torusGeometry args={[1.3, 0.14, 12, 48]} />
          <meshStandardMaterial {...METAL.brushed} />
        </mesh>
        <mesh>
          <torusGeometry args={[1.1, 0.025, 8, 48]} />
          <primitive object={seamMat} attach="material" />
        </mesh>
      </group>

      {/* core */}
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[0.55, 2]} />
        <primitive object={coreMat} attach="material" />
      </mesh>
      <pointLight color="#FF5A00" intensity={6} distance={6} decay={2} />
    </group>
  );
});

export default ReactorMesh;
