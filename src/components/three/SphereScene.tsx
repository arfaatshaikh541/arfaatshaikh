"use client";

import { useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { PerspectiveCamera, PerformanceMonitor } from "@react-three/drei";
import { Lighting } from "./Lighting";
import { CameraRig } from "./CameraRig";
import { SphereRig } from "./SphereRig";
import { Particles } from "./Particles";
import { PostFX } from "./PostFX";
import { useWebGLSupport } from "./useWebGLSupport";
import { SphereFallback } from "./SphereFallback";
import { SphereErrorBoundary } from "./SphereErrorBoundary";

function SceneContent({ highQuality }: { highQuality: boolean }) {
  return (
    <>
      <PerspectiveCamera makeDefault fov={42} position={[0, 0, 6.4]} near={0.1} far={40} />
      <CameraRig />
      <Lighting />
      <SphereRig />
      <Particles />
      <PostFX highQuality={highQuality} />
    </>
  );
}

export function SphereScene() {
  const webglSupported = useWebGLSupport();
  const [visible, setVisible] = useState(true);
  const [highQuality, setHighQuality] = useState(true);

  useEffect(() => {
    const onVisibility = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  if (webglSupported !== true) {
    return <SphereFallback />;
  }

  return (
    <SphereErrorBoundary>
      <Canvas
        dpr={[1, highQuality ? 2 : 1.25]}
        frameloop={visible ? "always" : "never"}
        gl={{ antialias: false, powerPreference: "high-performance", alpha: false }}
        onCreated={({ gl }) => {
          gl.setClearColor("#000000", 1);
        }}
      >
        <PerformanceMonitor onDecline={() => setHighQuality(false)} />
        <SceneContent highQuality={highQuality} />
      </Canvas>
    </SphereErrorBoundary>
  );
}
