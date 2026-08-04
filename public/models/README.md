# Models

`hero-core-v2.glb` is the hero object's primary visual, loaded by `src/components/three/CoreModel.tsx` via `@react-three/drei`'s `useGLTF`, inside a `<Suspense>` boundary so the rest of the scene renders immediately while it streams in.

Unlike the original `hero-core.glb` (a single baked mesh with a crack pattern painted into a texture), this is a genuinely multi-part sculpt — 14 separate meshes named `tripo_part_0`..`tripo_part_13` by the AI tool (Tripo) that generated it, with the crack pattern on the core sphere as real sculpted geometry and no textures at all (flat PBR material factors only). `CoreModel.tsx` assigns a dark obsidian material to the core part and a shared polished-chrome material to everything else, and groups the remaining parts into a left wing, right wing, and base by each part's own bounding-box center — see `tripo_part_*` name lists in `CoreModel.tsx` — so the wings can drift outward under hover/click instead of the whole object only ever moving as one rigid piece.

It started as a ~2M-triangle / 46 MB export with no textures — again far too heavy for real-time use — and was optimized with [`@gltf-transform`](https://gltf-transform.dev/)'s `functions` API (not the CLI, since per-part simplify ratios aren't exposed there) down to ~59k triangles / ~1 MB: `weldPrimitive` + `simplifyPrimitive` per mesh (meshoptimizer, tiered ratios — the core sphere kept more detail than the two big blades, which are simple swept shapes that lost almost all of their density without changing silhouette), then `prune`/`dedup`/`quantize`. No Draco/Meshopt geometry compression was applied, so it stays a plain glTF parseable by `GLTFLoader` with no extra decoder assets to ship for static hosting.

If you regenerate or replace this asset: keep it as separately named mesh parts (not merged into one mesh) if you want the wing-separation animation to keep working, and re-run an equivalent tiered-simplify pipeline before committing a new version — nothing here needs to exceed a few MB.

The original `hero-core.glb` (single mesh, baked textures) has been removed now that `CoreModel.tsx` no longer references it.
