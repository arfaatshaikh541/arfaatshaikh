"use client";

import { useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { EdgeBeam } from "@/components/three/EdgeBeam";
import { usePointerParallax } from "@/components/three/usePointerParallax";
import { useIsMobile, usePrefersReducedMotion, particleCount } from "@/lib/performance";

interface NeuralNode {
  position: THREE.Vector3;
  parent: number | null;
  phase: number;
}

function buildNeuralGraph(count: number): NeuralNode[] {
  const nodes: NeuralNode[] = [{ position: new THREE.Vector3(0, 0, 0), parent: null, phase: 0 }];
  for (let i = 1; i < count; i += 1) {
    const radius = 1.4 + Math.random() * 2.6;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const position = new THREE.Vector3(
      radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.sin(phi) * Math.sin(theta) * 0.7,
      radius * Math.cos(phi)
    );
    const parent = Math.floor(Math.random() * i);
    nodes.push({ position, parent, phase: Math.random() * Math.PI * 2 });
  }
  return nodes;
}

interface NeuralSceneProps {
  progressRef?: MutableRefObject<number>;
}

export function NeuralScene({ progressRef }: NeuralSceneProps) {
  const isMobile = useIsMobile();
  const reducedMotion = usePrefersReducedMotion();
  const nodeCount = particleCount(isMobile ? 16 : 26, isMobile, reducedMotion);
  const nodes = useMemo(() => buildNeuralGraph(nodeCount), [nodeCount]);

  const group = useRef<THREE.Group>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const coreMat = useRef<any>(null);
  const nodeMeshes = useRef<(THREE.Mesh | null)[]>([]);
  const pointer = usePointerParallax();

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (group.current) {
      group.current.rotation.y += delta * 0.035;
      if (!reducedMotion) {
        group.current.rotation.x = THREE.MathUtils.lerp(
          group.current.rotation.x,
          pointer.current.y * 0.15,
          0.03
        );
      }
    }

    if (coreRef.current) {
      coreRef.current.scale.setScalar(1 + Math.sin(t * 1.4) * 0.06 + progress * 0.2);
    }
    if (coreMat.current) {
      coreMat.current.uTime = t;
      coreMat.current.uActivation = 0.7 + progress * 0.3;
    }

    nodeMeshes.current.forEach((mesh, index) => {
      if (!mesh) return;
      const node = nodes[index];
      const activation = 0.4 + 0.6 * Math.max(0, Math.sin(t * 0.8 + node.phase - progress * 3));
      const material = mesh.material as THREE.MeshStandardMaterial;
      material.emissiveIntensity = activation * (0.6 + progress * 0.8);
    });
  });

  return (
    <group ref={group}>
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[0.55, 2]} />
        <energyMaterial
          ref={coreMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#7A2200"
          uColorBright="#FF9A3D"
          uFresnelPower={1.2}
          uNoiseScale={2.4}
          uIntensity={1.5}
        />
      </mesh>

      {nodes.slice(1).map((node, index) => (
        <mesh
          key={index}
          position={node.position}
          ref={(el) => {
            nodeMeshes.current[index + 1] = el;
          }}
        >
          <sphereGeometry args={[0.08, 12, 12]} />
          <meshStandardMaterial
            color="#0b0b0b"
            metalness={0.7}
            roughness={0.35}
            emissive="#FF5A00"
            emissiveIntensity={0.5}
          />
        </mesh>
      ))}

      {nodes.slice(1).map((node, index) => {
        const parentIndex = node.parent ?? 0;
        const parentPos = nodes[parentIndex].position;
        return (
          <EdgeBeam
            key={`edge-${index}`}
            from={parentPos}
            to={node.position}
            color="#FF7A1A"
            width={0.018}
            speed={0.4 + Math.random() * 0.5}
          />
        );
      })}
    </group>
  );
}
