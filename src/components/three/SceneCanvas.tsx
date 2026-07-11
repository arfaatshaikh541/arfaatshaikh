"use client";

import { Suspense, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { Bloom, DepthOfField, EffectComposer, Noise, Vignette } from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import { WebGLGate } from "./WebGLGate";
import { SceneErrorBoundary } from "./SceneErrorBoundary";
import { ScenePoster } from "./ScenePoster";
import { useDocumentVisible, useIsMobile, usePrefersReducedMotion } from "@/lib/performance";
import { getDprCap } from "@/lib/three";
import type { SceneId } from "@/types";
import { cn } from "@/lib/utils";

interface SceneCanvasProps {
  scene: SceneId;
  children: ReactNode;
  cameraPosition?: [number, number, number];
  fov?: number;
  className?: string;
  postFX?: boolean;
  interactive?: boolean;
}

export function SceneCanvas({
  scene,
  children,
  cameraPosition = [0, 0, 9],
  fov = 42,
  className,
  postFX = true,
  interactive = true,
}: SceneCanvasProps) {
  const isMobile = useIsMobile();
  const reducedMotion = usePrefersReducedMotion();
  const visible = useDocumentVisible();
  const dpr = getDprCap(isMobile);

  return (
    <div className={cn("relative h-full w-full overflow-hidden bg-black", className)}>
      <ScenePoster scene={scene} />
      <WebGLGate fallback={<ScenePoster scene={scene} />}>
        <SceneErrorBoundary fallback={<ScenePoster scene={scene} />}>
          <Suspense fallback={null}>
            <Canvas
              dpr={dpr}
              gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
              camera={{ position: cameraPosition, fov }}
              frameloop={visible ? "always" : "never"}
              style={{ position: "absolute", inset: 0, pointerEvents: interactive ? "auto" : "none" }}
            >
              <color attach="background" args={["#000000"]} />
              <fog attach="fog" args={["#000000", 8, 26]} />
              <ambientLight intensity={0.25} color="#3a2015" />
              <directionalLight position={[6, 8, 5]} intensity={0.6} color="#ff9a3d" />
              <pointLight position={[-6, -4, -3]} intensity={0.4} color="#ff5a00" />
              {children}
              {postFX && !reducedMotion && (
                <EffectComposer multisampling={isMobile ? 0 : 4}>
                  <Bloom
                    intensity={isMobile ? 0.5 : 0.85}
                    luminanceThreshold={0.22}
                    luminanceSmoothing={0.35}
                    mipmapBlur
                  />
                  {!isMobile ? (
                    <DepthOfField focusDistance={0.015} focalLength={0.04} bokehScale={2.2} />
                  ) : (
                    <></>
                  )}
                  <Noise opacity={0.02} blendFunction={BlendFunction.OVERLAY} />
                  <Vignette eskil={false} offset={0.25} darkness={0.85} />
                </EffectComposer>
              )}
            </Canvas>
          </Suspense>
        </SceneErrorBoundary>
      </WebGLGate>
    </div>
  );
}
