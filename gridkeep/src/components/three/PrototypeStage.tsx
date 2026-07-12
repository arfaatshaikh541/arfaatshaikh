"use client";

import type { ReactNode } from "react";
import CanvasStage from "./CanvasStage";
import Lighting from "./Lighting";
import { ContactShadows } from "@react-three/drei";

type Props = {
  title: string;
  description: string;
  className?: string;
  cameraPosition?: [number, number, number];
  fov?: number;
  children: ReactNode;
  groundY?: number;
};

/** Standard prototype presentation: lighting rig + contact shadow floor + the scene. */
export default function PrototypeStage({
  title,
  description,
  className,
  cameraPosition,
  fov,
  children,
  groundY = -1,
}: Props) {
  return (
    <CanvasStage
      title={title}
      description={description}
      className={className}
      cameraPosition={cameraPosition}
      fov={fov}
    >
      <Lighting />
      {children}
      <ContactShadows position={[0, groundY, 0]} opacity={0.55} scale={8} blur={2.4} far={3} color="#000000" />
    </CanvasStage>
  );
}
