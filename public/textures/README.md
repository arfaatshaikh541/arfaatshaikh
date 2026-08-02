# Textures

The sphere's outer fire jets, smoke, and embers are fully procedural — generated at runtime with GLSL noise (`src/shaders/fireFragment.glsl`, `src/shaders/noise.glsl`) and a canvas-generated soft dot sprite (`src/components/three/Particles.tsx`). No external texture files are required for those.

`basecolor-dark-metal.jpg` and `crack-alpha.png` are the two exceptions: derived textures for the hero GLB (`public/models/hero-core.glb`) that let `src/components/three/CoreModel.tsx` show a real, animated fire core (`src/components/three/FireCore.tsx`) through the model's cracks instead of a flat painted-on glow. Both are generated from the GLB's own baked basecolor bake (extracted from the `.glb`'s embedded BIN chunk) by classifying each pixel's "redness" (`R - (G+B)/2`, smoothstepped and blurred):

- **`basecolor-dark-metal.jpg`** — the same basecolor bake with its lava/crack regions crushed toward black (kept at ~3% brightness) and its metal-shard regions darkened to ~34% brightness. Used as the model's diffuse `map` so the shell reads as dark gunmetal instead of a lit-up lava ball.
- **`crack-alpha.png`** — a sparse alpha cutout isolating only the brightest, thinnest crack/vein lines (top ~15-20% reddest pixels) as near-zero alpha, everything else near-opaque. Used as `material.alphaMap` with `alphaTest` so those thin lines are true holes in the geometry, not just a texture — letting `FireCore`'s shader-driven glow show through instead of a baked pattern.

Regenerating either from a new bake: same redness formula, `threshold≈45` for the dark map (broad, crushes both patches and lines), `threshold≈125` for the alpha cutout (narrow, thin lines only) — see the git history for the exact Python/Pillow script if reproducing from scratch. Both textures load through a plain `TextureLoader` (`useTexture`, not `GLTFLoader`), so `CoreModel.tsx` sets `flipY = false` on each to match the model's own glTF-convention UVs.

To use a real flame sprite sheet instead of the procedural outer-jet shader:

1. Add the sprite sheet here, e.g. `public/textures/flame-sprite-sheet.png`.
2. In `src/components/three/Flames.tsx`, replace the `shaderMaterial` on each `FlameJet` with a `meshBasicMaterial` using `useTexture("/textures/flame-sprite-sheet.png")` from `@react-three/drei`, animate the UV offset per frame to step through sprite sheet frames, and keep `blending={THREE.AdditiveBlending}` and `depthWrite={false}`.
