"use client";

import { useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { PerspectiveCamera, PerformanceMonitor, Environment, Lightformer } from "@react-three/drei";
import { Lighting } from "./Lighting";
import { CameraRig } from "./CameraRig";
import { SphereRig } from "./SphereRig";
import { Particles } from "./Particles";
import { PostFX } from "./PostFX";
import { useWebGLSupport } from "./useWebGLSupport";
import { SphereFallback } from "./SphereFallback";
import { SphereErrorBoundary } from "./SphereErrorBoundary";

// A fully procedural environment (no HDRI file, no network fetch — drei
// bakes these Lightformer shapes into a small PMREM cubemap at runtime) so
// the model's metal blades pick up real reflections instead of only flat
// direct-light highlights. `background={false}` keeps it out of the visible
// backdrop — it only feeds material reflections. Two-tone by design: a warm
// rect above/behind echoes the core's own glow bouncing off the metal, a
// cool thin rim strip to the side gives the blades a hard specular edge for
// contrast, and a very dim ambient ring keeps the rest of each blade from
// going flat black.
function HeroEnvironment() {
  return (
    <Environment resolution={128} background={false}>
      <Lightformer form="rect" intensity={3} color="#ff3a1a" position={[1.5, 2.5, 2]} scale={[5, 5, 1]} />
      <Lightformer form="rect" intensity={1.8} color="#3ac6ff" position={[-3, 0.5, 1.5]} scale={[0.5, 4, 1]} />
      <Lightformer form="ring" intensity={0.5} color="#402018" position={[0, -3, -2]} scale={[6, 6, 1]} />
    </Environment>
  );
}

function SceneContent({ highQuality }: { highQuality: boolean }) {
  return (
    <>
      <PerspectiveCamera makeDefault fov={42} position={[0, 0, 6.4]} near={0.1} far={40} />
      <CameraRig />
      <Lighting />
      <HeroEnvironment />
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
