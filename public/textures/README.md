# Textures

The sphere's fire, smoke, and embers are fully procedural — generated at runtime with GLSL noise (`src/shaders/fireFragment.glsl`, `src/shaders/noise.glsl`) and a canvas-generated soft dot sprite (`src/components/three/Particles.tsx`). No external texture files are required for the site to work.

This folder is a placeholder for anyone who wants to swap the procedural flames for authored assets — for example, a hand-painted flame sprite sheet or a scanned volcanic-rock normal/roughness map.

To use a real flame sprite sheet instead of the procedural shader:

1. Add the sprite sheet here, e.g. `public/textures/flame-sprite-sheet.png`.
2. In `src/components/three/Flames.tsx`, replace the `shaderMaterial` on each `FlameJet` with a `meshBasicMaterial` using `useTexture("/textures/flame-sprite-sheet.png")` from `@react-three/drei`, animate the UV offset per frame to step through sprite sheet frames, and keep `blending={THREE.AdditiveBlending}` and `depthWrite={false}`.
3. To add real surface detail to the shell (`src/components/three/SphereShell.tsx`), add a roughness/normal map here (e.g. `public/textures/obsidian-normal.jpg`) and mix it into `shellFragment.glsl` alongside the existing procedural `fbm()` roughness term.
