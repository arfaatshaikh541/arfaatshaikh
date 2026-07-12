"use client";

import { Suspense, useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { View, AdaptiveDpr, PerformanceMonitor, Preload } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette, Noise } from "@react-three/postprocessing";
import { useWebGLSupport } from "@/hooks/useWebGLSupport";
import { useReducedMotion } from "@/hooks/useReducedMotion";

/**
 * One persistent, viewport-fixed WebGL context for the entire site.
 * Every <CanvasStage> below tunnels a scissor-rendered <View> into this
 * canvas instead of mounting its own — browsers cap live WebGL contexts
 * (as low as 8 on mobile Safari), and this page has dozens of prototype
 * scenes on a single route.
 */
export default function SceneRoot() {
  const webglSupported = useWebGLSupport();
  const reducedMotion = useReducedMotion();
  const [hidden, setHidden] = useState(false);
  const [dpr, setDpr] = useState<[number, number]>([1, 1.6]);

  useEffect(() => {
    const onVisibility = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  if (webglSupported === false) return null;

  return (
    <Canvas
      shadows
      dpr={dpr}
      frameloop={hidden ? "never" : "always"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      className="!pointer-events-none !fixed !inset-0 !z-10 !h-screen !w-screen"
      onCreated={({ gl }) => {
        gl.setClearColor("#000000", 0);
      }}
    >
      <PerformanceMonitor onIncline={() => setDpr([1, 1.8])} onDecline={() => setDpr([1, 1])} />
      <AdaptiveDpr pixelated={false} />
      <Suspense fallback={null}>
        <View.Port />
        <Preload all />
      </Suspense>
      {!reducedMotion && (
        <EffectComposer multisampling={0} enableNormalPass={false}>
          <Bloom intensity={0.5} luminanceThreshold={0.24} luminanceSmoothing={0.35} mipmapBlur />
          <Noise opacity={0.018} />
          <Vignette eskil={false} offset={0.25} darkness={0.82} />
        </EffectComposer>
      )}
    </Canvas>
  );
}
