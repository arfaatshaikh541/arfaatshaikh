"use client";

import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { View, PerspectiveCamera } from "@react-three/drei";
import SceneErrorBoundary from "./SceneErrorBoundary";
import { useWebGLSupport } from "@/hooks/useWebGLSupport";

type CanvasStageProps = {
  title: string;
  description: string;
  children: ReactNode;
  className?: string;
  cameraPosition?: [number, number, number];
  fov?: number;
};

function PosterFallback({ title }: { title: string }) {
  return (
    <div
      className="gk-grid-bg relative flex h-full w-full items-center justify-center overflow-hidden border border-gk-steel bg-gk-graphite"
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-gk-black via-gk-graphite to-gk-black" />
      <div className="relative flex flex-col items-center gap-3 px-6 text-center">
        <span className="gk-eyebrow">Prototype Render Unavailable</span>
        <span className="font-display text-2xl text-gk-white/70">{title}</span>
        <span className="h-px w-16 bg-gk-orange" />
      </div>
    </div>
  );
}

/**
 * Tunnels a scissor-rendered scene into the single shared <SceneRoot> canvas
 * (see components/three/SceneRoot.tsx) instead of mounting its own WebGL
 * context — keeps the whole site under the browser's live-context budget.
 */
export default function CanvasStage({
  title,
  description,
  children,
  className = "",
  cameraPosition = [3.4, 1.6, 4.6],
  fov = 38,
}: CanvasStageProps) {
  const webglSupported = useWebGLSupport();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => setReady(true), 6500);
    return () => clearTimeout(timeout);
  }, []);

  const containerId = useMemo(
    () => `gk-scene-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
    [title]
  );

  if (webglSupported === false) {
    return (
      <div className={className}>
        <PosterFallback title={title} />
        <p className="gk-visually-hidden">{description}</p>
      </div>
    );
  }

  return (
    <div className={`relative bg-gk-black ${className}`} role="img" aria-label={`${title}. ${description}`} id={containerId}>
      <SceneErrorBoundary fallback={<PosterFallback title={title} />}>
        <View className="h-full w-full">
          <PerspectiveCamera
            makeDefault
            position={cameraPosition}
            fov={fov}
            near={0.1}
            far={30}
            onUpdate={(cam) => cam.lookAt(0, 0, 0)}
          />
          <fog attach="fog" args={["#050505", 9, 22]} />
          <Suspense fallback={null}>
            <group>{children}</group>
          </Suspense>
        </View>
      </SceneErrorBoundary>
      <p className="gk-visually-hidden">{description}</p>
      {!ready && (
        <span className="gk-visually-hidden" role="status">
          Loading {title}
        </span>
      )}
    </div>
  );
}
