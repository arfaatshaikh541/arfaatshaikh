"use client";

import { Float } from "@react-three/drei";
import type { ModelVariant } from "@/types";
import { useReducedMotion } from "@/lib/useReducedMotion";
import ReactorMesh from "./models/ReactorMesh";
import NeuralMesh from "./models/NeuralMesh";
import AutomationMesh from "./models/AutomationMesh";
import ArchitectureMesh from "./models/ArchitectureMesh";
import VaultMesh from "./models/VaultMesh";
import ClusterMesh from "./models/ClusterMesh";
import CloudMesh from "./models/CloudMesh";
import GridMesh from "./models/GridMesh";
import EcosystemMesh from "./models/EcosystemMesh";

interface PrototypeModelProps {
  variant: ModelVariant;
  scale?: number;
  float?: boolean;
}

export default function PrototypeModel({ variant, scale = 1, float = true }: PrototypeModelProps) {
  const reducedMotion = useReducedMotion();
  const mesh = (() => {
    switch (variant) {
      case "reactor":
        return <ReactorMesh scale={scale} />;
      case "neural":
        return <NeuralMesh scale={scale} />;
      case "automation":
        return <AutomationMesh scale={scale} />;
      case "architecture":
        return <ArchitectureMesh scale={scale} />;
      case "vault":
        return <VaultMesh scale={scale} />;
      case "cluster":
        return <ClusterMesh scale={scale} />;
      case "cloud":
        return <CloudMesh scale={scale} />;
      case "grid":
        return <GridMesh scale={scale} />;
      case "ecosystem":
        return <EcosystemMesh scale={scale} />;
      default:
        return <ReactorMesh scale={scale} />;
    }
  })();

  return (
    <>
      <ambientLight intensity={0.18} color="#3a2013" />
      <directionalLight position={[3, 4, 3]} intensity={0.6} color="#FFA048" />
      <directionalLight position={[-3, -2, -3]} intensity={0.25} color="#C94700" />
      {float && !reducedMotion ? (
        <Float speed={1.4} rotationIntensity={0.25} floatIntensity={0.5}>
          {mesh}
        </Float>
      ) : (
        mesh
      )}
    </>
  );
}
