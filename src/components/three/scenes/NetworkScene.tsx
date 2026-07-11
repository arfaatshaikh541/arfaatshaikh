"use client";

import { useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { EdgeBeam } from "@/components/three/EdgeBeam";
import { usePrefersReducedMotion } from "@/lib/performance";

interface NetworkSceneProps {
  progressRef?: MutableRefObject<number>;
}

const NODE_LABELS = ["Customer", "Sales", "Service", "Finance", "Operations", "Analytics"];

export function NetworkScene({ progressRef }: NetworkSceneProps) {
  const group = useRef<THREE.Group>(null);
  const hubMat = useRef<any>(null);
  const nodeRefs = useRef<(THREE.Mesh | null)[]>([]);
  const duplicateRefs = useRef<(THREE.Mesh | null)[]>([]);
  const reducedMotion = usePrefersReducedMotion();

  const nodes = useMemo(
    () =>
      NODE_LABELS.map((label, i) => {
        const angle = (i / NODE_LABELS.length) * Math.PI * 2;
        return {
          label,
          position: new THREE.Vector3(Math.cos(angle) * 2.6, Math.sin(angle * 0.6) * 0.6, Math.sin(angle) * 2.6),
          isAnalytics: label === "Analytics",
        };
      }),
    []
  );

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (group.current) group.current.rotation.y += delta * (reducedMotion ? 0.01 : 0.035);

    if (hubMat.current) {
      hubMat.current.uTime = t;
      hubMat.current.uActivation = 0.4 + progress * 0.6;
    }

    nodeRefs.current.forEach((mesh, index) => {
      if (!mesh) return;
      const node = nodes[index];
      const material = mesh.material as THREE.MeshStandardMaterial;
      const boost = node.isAnalytics ? progress * 1.2 : progress * 0.6;
      material.emissiveIntensity = 0.35 + boost;
    });

    duplicateRefs.current.forEach((mesh) => {
      if (!mesh) return;
      const scale = Math.max(0, 0.14 * (1 - progress * 1.4));
      mesh.scale.setScalar(scale);
    });
  });

  return (
    <group ref={group}>
      <mesh>
        <icosahedronGeometry args={[0.55, 1]} />
        <energyMaterial
          ref={hubMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#7A2200"
          uColorBright="#FF9A3D"
          uFresnelPower={1.4}
          uNoiseScale={1.4}
          uIntensity={1.3}
        />
      </mesh>

      {nodes.map((node, i) => (
        <group key={node.label}>
          <mesh
            position={node.position}
            ref={(el) => {
              nodeRefs.current[i] = el;
            }}
          >
            <octahedronGeometry args={[0.22, 0]} />
            <meshStandardMaterial
              color="#0d0d0d"
              metalness={0.8}
              roughness={0.25}
              emissive={node.isAnalytics ? "#FF9A3D" : "#FF5A00"}
              emissiveIntensity={0.35}
            />
          </mesh>
          <mesh
            position={node.position.clone().add(new THREE.Vector3(0.3, 0.25, 0.15))}
            ref={(el) => {
              duplicateRefs.current[i] = el;
            }}
          >
            <octahedronGeometry args={[0.14, 0]} />
            <meshStandardMaterial color="#3a1a08" metalness={0.4} roughness={0.6} transparent opacity={0.5} />
          </mesh>
          <EdgeBeam from={new THREE.Vector3(0, 0, 0)} to={node.position} width={0.016} color={node.isAnalytics ? "#FF9A3D" : "#C84400"} />
        </group>
      ))}
    </group>
  );
}
