"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

const MODEL_PATH = "/models/hero-core.glb";
// The model's ball-and-blade silhouette, scaled so its longest axis lands
// here. The procedural outer shell has a 1.72 radius (3.44 diameter) — this
// is sized to read as the dominant sculptural layer around/beyond it, with
// the shell, core, and particles glowing through its natural gaps.
const TARGET_DIAMETER = 4.3;

export function CoreModel() {
  const { scene } = useGLTF(MODEL_PATH);
  const groupRef = useRef<THREE.Group>(null);
  const materialRef = useRef<THREE.MeshStandardMaterial | null>(null);

  // One-time setup derived from the loaded asset: recenter the mesh on its
  // own geometry (the export's pivot sits at the bottom of the model, not
  // its visual center), compute a normalized scale, and turn the baked
  // basecolor texture into an emissive map too so the painted-on cracks can
  // brighten on hover/pulse/scroll instead of staying a flat baked image.
  // Runs once per loaded `scene` (a stable, cached reference from
  // useGLTF) — mutating here rather than in an effect avoids a first-frame
  // flash at the wrong scale/position.
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
    material.metalness = 0.55;
    material.roughness = 0.32;
    material.emissiveMap = material.map;
    material.emissive = new THREE.Color("#ff2a1a");
    material.emissiveIntensity = 0.12;
    material.transparent = true;
    material.opacity = 1;
    material.needsUpdate = true;
    materialRef.current = material;

    const maxDimension = Math.max(size.x, size.y, size.z) || 1;
    return TARGET_DIAMETER / maxDimension;
  }, [scene]);

  useFrame(() => {
    const material = materialRef.current;
    const group = groupRef.current;

    if (material) {
      const heat =
        sceneState.coreBrightness * 0.22 +
        sceneState.hoverIntensity * 0.55 +
        sceneState.pulseStrength * 1.1;
      material.emissiveIntensity = THREE.MathUtils.lerp(
        material.emissiveIntensity,
        0.12 + heat,
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
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload(MODEL_PATH);
