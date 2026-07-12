"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { orangeEmissive } from "./materials";

/** A sagging cable/hose run between two points, built from a tube along a curve. */
export function CableRun({
  points,
  radius = 0.02,
  color = "#0b0b0b",
  sag = 0.12,
}: {
  points: Array<[number, number, number]>;
  radius?: number;
  color?: string;
  sag?: number;
}) {
  const curve = useMemo(() => {
    const vecs = points.map((p, i) => {
      const v = new THREE.Vector3(...p);
      if (i > 0 && i < points.length - 1) v.y -= sag;
      return v;
    });
    return new THREE.CatmullRomCurve3(vecs);
  }, [points, sag]);

  const geometry = useMemo(() => new THREE.TubeGeometry(curve, 24, radius, 8, false), [curve, radius]);
  const material = useMemo(
    () => new THREE.MeshStandardMaterial({ color, roughness: 0.85, metalness: 0.1 }),
    [color]
  );

  return <mesh geometry={geometry} material={material} castShadow />;
}

/** Pulsing orange status light — small emissive capsule used everywhere as a "system alive" cue. */
export function StatusLight({
  position,
  scale = 1,
  speed = 1.4,
  offset = 0,
}: {
  position: [number, number, number];
  scale?: number;
  speed?: number;
  offset?: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const material = useMemo(() => orangeEmissive(2.4), []);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.getElapsedTime() * speed + offset;
    const pulse = 1.6 + Math.sin(t) * 1.1;
    (ref.current.material as THREE.MeshStandardMaterial).emissiveIntensity = Math.max(0.4, pulse);
  });

  return (
    <mesh ref={ref} position={position} material={material} castShadow>
      <sphereGeometry args={[0.024 * scale, 12, 12]} />
    </mesh>
  );
}

/** Thin emissive strip used as a data-route / seam light on housings. */
export function EmissiveStrip({
  position,
  args,
  rotation,
  intensity = 1.8,
}: {
  position: [number, number, number];
  args: [number, number, number];
  rotation?: [number, number, number];
  intensity?: number;
}) {
  const material = useMemo(() => orangeEmissive(intensity), [intensity]);
  return (
    <mesh position={position} rotation={rotation} material={material}>
      <boxGeometry args={args} />
    </mesh>
  );
}

/** A rectangular machined panel with a chamfer-style bevel look via slightly inset edge box. */
export function Panel({
  position,
  args,
  material,
  rotation,
  castShadow = true,
}: {
  position: [number, number, number];
  args: [number, number, number];
  material: THREE.Material;
  rotation?: [number, number, number];
  castShadow?: boolean;
}) {
  return (
    <mesh position={position} rotation={rotation} material={material} castShadow={castShadow} receiveShadow>
      <boxGeometry args={args} />
    </mesh>
  );
}

/** Data-pulse traveling along a straight or curved path — used to show "data flowing" through hardware. */
export function DataPulse({
  from,
  to,
  speed = 0.6,
  delay = 0,
  radius = 0.014,
}: {
  from: [number, number, number];
  to: [number, number, number];
  speed?: number;
  delay?: number;
  radius?: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const material = useMemo(() => orangeEmissive(3.2), []);
  const start = useMemo(() => new THREE.Vector3(...from), [from]);
  const end = useMemo(() => new THREE.Vector3(...to), [to]);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = ((clock.getElapsedTime() * speed + delay) % 1 + 1) % 1;
    ref.current.position.lerpVectors(start, end, t);
    const visible = t > 0.02 && t < 0.98;
    ref.current.visible = visible;
  });

  return (
    <mesh ref={ref} material={material}>
      <sphereGeometry args={[radius, 8, 8]} />
    </mesh>
  );
}
