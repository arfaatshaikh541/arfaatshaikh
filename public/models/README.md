# Models

Not currently used — the sphere is built entirely from procedural `THREE.SphereGeometry` + custom shaders (see `src/components/three/`), so no `.glb`/`.gltf` model files are required.

This folder exists for future secondary 3D assets (e.g. a GRIDKEEP logo mark rendered in 3D, or scene set-dressing). Load any model added here lazily with `@react-three/drei`'s `useGLTF`, wrapped in `React.Suspense`, and dispose of it in a cleanup effect to avoid leaking GPU memory.
