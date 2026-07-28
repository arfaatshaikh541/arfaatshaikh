"use client";

import { useRef, useState } from "react";
import { useFrame, extend, type ThreeElement } from "@react-three/fiber";
import { EffectComposer, Bloom, Vignette, ChromaticAberration } from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";
import { HeatDistortionEffect } from "./effects/HeatDistortionEffect";

extend({ HeatDistortionEffect });

declare module "@react-three/fiber" {
  interface ThreeElements {
    heatDistortionEffect: ThreeElement<typeof HeatDistortionEffect>;
  }
}

function quantize(value: number, step: number): number {
  return Math.round(value / step) * step;
}

export function PostFX({ highQuality }: { highQuality: boolean }) {
  const heatRef = useRef<HeatDistortionEffect>(null);
  const [bloomIntensity, setBloomIntensity] = useState(0.55);
  const [vignetteDarkness, setVignetteDarkness] = useState(0.55);
  const [chromaOffset, setChromaOffset] = useState(0.0006);

  useFrame(() => {
    if (heatRef.current) {
      heatRef.current.setIntensity(sceneState.heatDistortion);
    }

    const nextBloom = quantize(
      sceneState.bloomStrength + sceneState.hoverIntensity * 0.3 + sceneState.pulseStrength * 0.8,
      0.05
    );
    if (Math.abs(nextBloom - bloomIntensity) >= 0.05) setBloomIntensity(nextBloom);

    const nextVignette = quantize(sceneState.vignette, 0.03);
    if (Math.abs(nextVignette - vignetteDarkness) >= 0.03) setVignetteDarkness(nextVignette);

    const nextChroma = quantize(sceneState.chromaticAb * 0.006, 0.0004);
    if (Math.abs(nextChroma - chromaOffset) >= 0.0004) setChromaOffset(nextChroma);
  });

  return (
    <EffectComposer multisampling={highQuality ? 4 : 0}>
      <Bloom
        intensity={bloomIntensity}
        luminanceThreshold={0.15}
        luminanceSmoothing={0.35}
        mipmapBlur
        radius={0.85}
      />
      <ChromaticAberration
        offset={new THREE.Vector2(chromaOffset, chromaOffset * 0.6)}
        radialModulation={false}
        modulationOffset={0}
        blendFunction={BlendFunction.NORMAL}
      />
      <heatDistortionEffect ref={heatRef} args={[{ intensity: 0.15 }]} />
      <Vignette eskil={false} offset={0.35} darkness={vignetteDarkness} />
    </EffectComposer>
  );
}
