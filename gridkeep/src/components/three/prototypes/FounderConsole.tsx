"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive } from "../materials";
import { BoltField, circleOfBolts } from "../Instanced";
import { StatusLight } from "../Parts";
import { createSchematicTexture, createMatrixTexture, createSignatureTexture } from "../canvasTexture";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const CAPABILITIES = [
  { label: "Systems Architecture", value: 0.95 },
  { label: "Security Engineering", value: 0.88 },
  { label: "Automation & AI", value: 0.92 },
  { label: "Cloud Infrastructure", value: 0.86 },
  { label: "Commercial Execution", value: 0.9 },
];

export default function FounderConsole({ progressRef }: { progressRef?: ProgressRef }) {
  const frameMat = useMemo(() => gunmetal(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const consoleMat = useMemo(() => darkAnodized(), []);
  const ringMat = useMemo(() => orangeEmissive(1.8), []);
  const pulseRef = useRef<THREE.Mesh>(null);
  const ringGroup = useRef<THREE.Group>(null);

  const [signatureTex, setSignatureTex] = useState<THREE.CanvasTexture | null>(null);
  const [schematicTex, setSchematicTex] = useState<THREE.CanvasTexture | null>(null);
  const [matrixTex, setMatrixTex] = useState<THREE.CanvasTexture | null>(null);

  useEffect(() => {
    setSignatureTex(createSignatureTexture("AS"));
    setSchematicTex(createSchematicTexture());
    setMatrixTex(createMatrixTexture(CAPABILITIES));
  }, []);

  const boltPositions = useMemo(() => circleOfBolts(24, 0.98), []);

  useFrame((state, delta) => {
    const progress = progressRef?.current.value ?? 0.5;
    if (ringGroup.current) ringGroup.current.rotation.z += delta * 0.04;
    if (pulseRef.current) {
      const t = state.clock.elapsedTime;
      const s = 1 + Math.sin(t * 1.4) * 0.04 + progress * 0.15;
      pulseRef.current.scale.setScalar(s);
      const mat = pulseRef.current.material as THREE.MeshStandardMaterial;
      mat.opacity = 0.35 + Math.sin(t * 1.4) * 0.15;
    }
  });

  return (
    <group>
      {/* console base */}
      <mesh position={[0, -0.95, 0.3]} rotation={[-0.25, 0, 0]} material={consoleMat} castShadow receiveShadow>
        <boxGeometry args={[1.6, 0.1, 0.9]} />
      </mesh>
      <mesh position={[0, -1.25, 0.5]} material={frameMat} castShadow>
        <boxGeometry args={[1.5, 0.5, 0.4]} />
      </mesh>
      {Array.from({ length: 6 }).map((_, i) => (
        <mesh key={i} position={[-0.6 + i * 0.24, -0.9, 0.55]} rotation={[-0.25, 0, 0]} material={orangeEmissive(1)}>
          <boxGeometry args={[0.1, 0.02, 0.06]} />
        </mesh>
      ))}

      {/* circular orange system frame */}
      <group ref={ringGroup} position={[0, 0.2, -0.1]}>
        <mesh material={ringMat} castShadow>
          <torusGeometry args={[1.05, 0.045, 12, 48]} />
        </mesh>
        <mesh material={frameMat}>
          <torusGeometry args={[0.98, 0.06, 12, 48]} />
        </mesh>
        <BoltField positions={boltPositions} rotation={[Math.PI / 2, 0, 0]} radius={0.016} length={0.03} />
        <mesh ref={pulseRef}>
          <torusGeometry args={[1.05, 0.01, 8, 48]} />
          <meshBasicMaterial color="#ff5a1f" transparent opacity={0.4} />
        </mesh>
      </group>

      {/* founder identity plate — signature mark, not a portrait */}
      {signatureTex && (
        <mesh position={[0, 0.2, 0.02]}>
          <circleGeometry args={[0.82, 48]} />
          <meshStandardMaterial map={signatureTex} emissiveMap={signatureTex} emissive="#3a1408" emissiveIntensity={0.6} roughness={0.5} />
        </mesh>
      )}
      <mesh position={[0, 0.2, -0.05]} material={railMat}>
        <cylinderGeometry args={[0.9, 0.9, 0.03, 48]} />
      </mesh>

      {/* system architecture map panel */}
      {schematicTex && (
        <group position={[1.35, 0.15, 0.2]} rotation={[0, -0.5, 0]}>
          <mesh material={consoleMat} castShadow>
            <boxGeometry args={[0.85, 0.85, 0.03]} />
          </mesh>
          <mesh position={[0, 0, 0.02]}>
            <planeGeometry args={[0.78, 0.78]} />
            <meshStandardMaterial map={schematicTex} emissiveMap={schematicTex} emissive="#2a0f05" emissiveIntensity={0.5} />
          </mesh>
        </group>
      )}

      {/* personal capability matrix panel */}
      {matrixTex && (
        <group position={[-1.35, 0.05, 0.2]} rotation={[0, 0.5, 0]}>
          <mesh material={consoleMat} castShadow>
            <boxGeometry args={[0.9, 0.55, 0.03]} />
          </mesh>
          <mesh position={[0, 0, 0.02]}>
            <planeGeometry args={[0.84, 0.5]} />
            <meshStandardMaterial map={matrixTex} emissiveMap={matrixTex} emissive="#1a0a03" emissiveIntensity={0.4} />
          </mesh>
        </group>
      )}

      <StatusLight position={[-0.4, -0.75, 0.6]} offset={0} />
      <StatusLight position={[0.4, -0.75, 0.6]} offset={0.6} />
    </group>
  );
}
