"use client";

import { EffectComposer, Bloom, Vignette, Noise, ChromaticAberration } from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import { Vector2 } from "three";

export default function PostFX({ strong = false }: { strong?: boolean }) {
  return (
    <EffectComposer multisampling={0} enableNormalPass={false}>
      <Bloom
        intensity={strong ? 0.85 : 0.55}
        luminanceThreshold={0.22}
        luminanceSmoothing={0.35}
        mipmapBlur
        radius={0.6}
      />
      <ChromaticAberration offset={new Vector2(0.0006, 0.0006)} radialModulation={false} modulationOffset={0} />
      <Noise premultiply blendFunction={BlendFunction.OVERLAY} opacity={0.035} />
      <Vignette eskil={false} offset={0.25} darkness={0.85} />
    </EffectComposer>
  );
}
