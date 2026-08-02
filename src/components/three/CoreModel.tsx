"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF, useTexture } from "@react-three/drei";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";
import { FireCore } from "./FireCore";

const MODEL_PATH = "/models/hero-core.glb";
const ALPHA_MAP_PATH = "/textures/crack-alpha.png";
const DARK_MAP_PATH = "/textures/basecolor-dark-metal.jpg";
// The model's ball-and-blade silhouette, scaled so its longest axis lands
// here. The procedural outer shell has a 1.72 radius (3.44 diameter) — this
// is sized to read as the dominant sculptural layer around/beyond it, with
// the shell, core, and particles glowing through its natural gaps.
const TARGET_DIAMETER = 4.3;

export function CoreModel() {
  const { scene } = useGLTF(MODEL_PATH);
  const { alphaMap, darkMap } = useTexture({
    alphaMap: ALPHA_MAP_PATH,
    darkMap: DARK_MAP_PATH,
  });
  const groupRef = useRef<THREE.Group>(null);
  const materialRef = useRef<THREE.MeshStandardMaterial | null>(null);

  // One-time setup derived from the loaded asset: recenter the mesh on its
  // own geometry (the export's pivot sits at the bottom of the model, not
  // its visual center), compute a normalized scale, swap in the darkened
  // basecolor + crack alpha cutout (see below), and nest a FireCore inside
  // so it glows through the gaps the cutout opens up. Runs once per loaded
  // `scene` (a stable, cached reference from useGLTF) — mutating here
  // rather than in an effect avoids a first-frame flash at the wrong
  // scale/position.
  const scale = useMemo(() => {
    let mesh: THREE.Mesh | null = null;
    scene.traverse((child) => {
      if (child instanceof THREE.Mesh) mesh = child;
    });
    if (!mesh) return 1;

    const targetMesh = mesh as THREE.Mesh;
    targetMesh.geometry.computeBoundingBox();
    const box = targetMesh.geometry.boundingBox;
    if (!box) return 1;

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    targetMesh.position.set(-center.x, -center.y, -center.z);

    const material = targetMesh.material as THREE.MeshStandardMaterial;
    // The source asset's PBR factors default to fully metallic with no
    // roughness variation (metalness/roughness come only from its texture,
    // with implicit 1.0 scalar factors). Fully metallic surfaces have no
    // diffuse response and read as near-black without an environment map —
    // this scene is lit with direct lights only (no HDRI, to keep the
    // build self-contained for static export), so the scalars are pulled
    // down to something that still catches those lights directly.
    material.metalness = 0.45;
    material.roughness = 0.42;

    // The baked basecolor is a bright lava/crack pattern across nearly half
    // its surface — left as the diffuse map it reads as a lit-up lava ball,
    // not a dark metal shell with fire showing through gaps. Two derived
    // textures fix that (see public/textures/README.md for how they're
    // generated): a darkened basecolor as the new diffuse `map` (the same
    // bake with its lava/crack regions crushed toward black, so the shell
    // itself reads as dark gunmetal), and an alpha cutout that discards
    // those same regions outright so FireCore glows through the actual
    // gaps instead of a flat painted-on pattern. No emissiveMap here on
    // purpose — the bright original bake as an emissiveMap was washing the
    // whole shell back out to the same lit-lava look regardless of how dark
    // the diffuse map got. Emissive is a flat, untextured tint instead, so
    // hover/pulse warms the whole shell evenly and the real fire glow comes
    // only from FireCore showing through the cutouts.
    material.emissive = new THREE.Color("#ff2a1a");
    material.emissiveIntensity = 0.03;
    material.transparent = true;
    material.opacity = 1;

    // GLTFLoader always loads textures with flipY = false to match glTF's
    // UV convention; these two come from a plain TextureLoader (via
    // useTexture) instead, so they need the same flip disabled or they land
    // mirrored against the model's UVs.
    darkMap.flipY = false;
    darkMap.colorSpace = THREE.SRGBColorSpace;
    darkMap.needsUpdate = true;
    material.map = darkMap;

    alphaMap.flipY = false;
    alphaMap.needsUpdate = true;
    material.alphaMap = alphaMap;
    material.alphaTest = 0.45;
    material.depthWrite = true;

    material.needsUpdate = true;
    materialRef.current = material;

    const maxDimension = Math.max(size.x, size.y, size.z) || 1;
    return TARGET_DIAMETER / maxDimension;
  }, [scene, alphaMap, darkMap]);

  useFrame(() => {
    const material = materialRef.current;
    const group = groupRef.current;

    if (material) {
      const heat =
        sceneState.coreBrightness * 0.12 +
        sceneState.hoverIntensity * 0.4 +
        sceneState.pulseStrength * 0.9;
      material.emissiveIntensity = THREE.MathUtils.lerp(
        material.emissiveIntensity,
        0.015 + heat,
        0.08
      );
      material.opacity = THREE.MathUtils.lerp(
        material.opacity,
        1 - sceneState.splitAmount * 0.7,
        0.08
      );
    }

    if (group) {
      // A subtle swell as the narrative "opens" across chapters, on top of
      // the sharper click-pulse kick.
      const swell = 1 + sceneState.bladeOpen * 0.06 + sceneState.pulseStrength * 0.05;
      group.scale.setScalar(scale * swell);
    }
  });

  return (
    <group ref={groupRef} scale={scale}>
      <FireCore />
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload(MODEL_PATH);
useTexture.preload([ALPHA_MAP_PATH, DARK_MAP_PATH]);
