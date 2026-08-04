"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";
import { playHeroIntro } from "./HeroIntro";

const MODEL_PATH = "/models/hero-core-v2.glb";
// The model's ball-and-blade silhouette, scaled so its longest axis lands
// here. The procedural outer shell has a 1.72 radius (3.44 diameter) — this
// is sized to read as the dominant sculptural layer around/beyond it, with
// the shell, core, and particles glowing through its natural gaps.
const TARGET_DIAMETER = 4.3;

// This asset is a genuinely multi-part sculpt (14 separate meshes, named
// tripo_part_0..13 by the tool that generated it) rather than one baked
// mesh — the crack pattern on the core is real sculpted geometry, not a
// texture. Grouping them lets the two wings drift apart under
// hover/click instead of the whole object only ever moving as one rigid
// piece. Groups were assigned by inspecting each part's own bounding-box
// center (left/right by X sign, base pieces by low Y) — see
// tools/optimize.mjs in the asset-prep scratch work for the source data.
const CORE_PART = "tripo_part_1";
const LEFT_WING = new Set(["tripo_part_0", "tripo_part_5", "tripo_part_8"]);
const RIGHT_WING = new Set(["tripo_part_2", "tripo_part_7", "tripo_part_9", "tripo_part_10", "tripo_part_11"]);
const BASE_PARTS = new Set(["tripo_part_3", "tripo_part_4", "tripo_part_6", "tripo_part_12", "tripo_part_13"]);

interface DriftEntry {
  mesh: THREE.Mesh;
  direction: THREE.Vector3;
  driftScale: number;
}

export function CoreModel() {
  const { scene } = useGLTF(MODEL_PATH);
  const groupRef = useRef<THREE.Group>(null);
  const coreMaterialRef = useRef<THREE.MeshPhysicalMaterial | null>(null);
  const driftPartsRef = useRef<DriftEntry[]>([]);
  const smoothedHeat = useRef(0);

  // One-time setup derived from the loaded asset: recenter the whole rig
  // on its own combined geometry, compute a normalized scale, assign a
  // dark obsidian material (with the heartbeat glow) to the core sphere
  // and a shared polished-chrome material to every other part, and
  // record each non-core part's own local center as an outward "drift
  // direction" for the separation animation in useFrame. Runs once per
  // loaded `scene` (a stable, cached reference from useGLTF) — mutating
  // here rather than in an effect avoids a first-frame flash at the
  // wrong scale/position.
  const scale = useMemo(() => {
    const overallBox = new THREE.Box3().setFromObject(scene);
    const center = overallBox.getCenter(new THREE.Vector3());
    const size = overallBox.getSize(new THREE.Vector3());

    // Polished-chrome response matched to the reference art: high
    // metalness and low roughness so the HeroEnvironment Lightformer rig
    // carries real specular streaks across the blades.
    const chromeMaterial = new THREE.MeshPhysicalMaterial({
      color: "#c9cdd4",
      metalness: 0.88,
      roughness: 0.24,
      clearcoat: 0.35,
      clearcoatRoughness: 0.2,
      envMapIntensity: 1.1,
    });
    // The core sphere has no texture to fall back on — its cracked look
    // comes entirely from the sculpted grooves catching light, plus a
    // flat emissive tint animated the same way the old baked-texture
    // model's emissive map was (heartbeat pulse in useFrame below).
    const coreMaterial = new THREE.MeshPhysicalMaterial({
      color: "#0d0906",
      metalness: 0.65,
      roughness: 0.32,
      clearcoat: 0.5,
      clearcoatRoughness: 0.22,
      envMapIntensity: 0.9,
      emissive: new THREE.Color("#ff2a1a"),
      emissiveIntensity: 0.08,
    });
    coreMaterialRef.current = coreMaterial;

    const drift: DriftEntry[] = [];
    scene.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      const name = child.name;

      if (name === CORE_PART) {
        child.material = coreMaterial;
        return;
      }
      child.material = chromeMaterial;

      let driftScale = 0;
      if (LEFT_WING.has(name) || RIGHT_WING.has(name)) driftScale = 1;
      else if (BASE_PARTS.has(name)) driftScale = 0.35;
      if (driftScale === 0) return;

      child.geometry.computeBoundingBox();
      const box = child.geometry.boundingBox;
      if (!box) return;
      const partCenter = box.getCenter(new THREE.Vector3());
      const direction = partCenter.clone().sub(center);
      if (direction.lengthSq() < 1e-6) return;
      direction.normalize();
      drift.push({ mesh: child, direction, driftScale });
    });
    driftPartsRef.current = drift;

    scene.position.set(-center.x, -center.y, -center.z);

    // The model is only ever visible from this point on — Suspense keeps
    // this whole component unmounted until the GLB resolves, so this is
    // the first moment there's actually a mesh for the intro to animate.
    playHeroIntro();

    const maxDimension = Math.max(size.x, size.y, size.z) || 1;
    return TARGET_DIAMETER / maxDimension;
  }, [scene]);

  useFrame((state) => {
    const material = coreMaterialRef.current;
    const group = groupRef.current;
    const t = state.clock.elapsedTime;

    // A heartbeat, not a smooth breathing glow: a sharp, mostly-dark pulse
    // that spikes bright and fast, like the core is straining against
    // something about to give way. Speed and punch both ramp up with
    // turbulence/hover/click, so it reads as calm at rest and increasingly
    // frantic — closer to detonation — under interaction.
    const heartbeatSpeed =
      1.4 + sceneState.turbulence * 2.6 + sceneState.hoverIntensity * 1.6 + sceneState.pulseStrength * 3.5;
    const heartbeat = Math.pow(Math.max(0, Math.sin(t * heartbeatSpeed)), 3);
    const pulseAmplitude =
      0.22 + sceneState.coreBrightness * 0.35 + sceneState.hoverIntensity * 0.9 + sceneState.pulseStrength * 1.8;

    if (material) {
      const heat =
        sceneState.coreBrightness * 0.22 + sceneState.hoverIntensity * 0.55 + sceneState.pulseStrength * 1.1;
      smoothedHeat.current = THREE.MathUtils.lerp(smoothedHeat.current, heat, 0.08);
      material.emissiveIntensity = 0.08 + smoothedHeat.current + heartbeat * pulseAmplitude;
    }

    // The wings drift outward along each part's own resting direction —
    // a literal "coming apart" instead of the whole rig only ever moving
    // as one rigid piece. Driven by the same hover/click signals already
    // wired up elsewhere (not the old scroll-chapter fields, which have
    // no live writer since the chapter system was retired), so it just
    // works with whatever's already driving the rest of the hero.
    const driftAmount = sceneState.hoverIntensity * 0.16 + sceneState.pulseStrength * 0.42;
    for (const { mesh, direction, driftScale } of driftPartsRef.current) {
      mesh.position.lerp(
        direction.clone().multiplyScalar(driftAmount * driftScale),
        0.12
      );
    }

    if (group) {
      // A subtle swell as the narrative "opens" across chapters, plus the
      // sharper click-pulse kick, plus a faint throb in lockstep with the
      // heartbeat glow so the whole object physically strains on each beat.
      const swell =
        1 +
        sceneState.bladeOpen * 0.06 +
        sceneState.pulseStrength * 0.05 +
        heartbeat * 0.025 * (0.4 + sceneState.hoverIntensity + sceneState.pulseStrength);
      group.scale.setScalar(scale * swell * sceneState.introScale);
    }
  });

  return (
    <group ref={groupRef} scale={scale}>
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload(MODEL_PATH);
