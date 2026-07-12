"use client";

import { useMemo, useRef, useLayoutEffect } from "react";
import * as THREE from "three";
import { boltMaterial } from "./materials";

type BoltFieldProps = {
  positions: Array<[number, number, number]>;
  rotation?: [number, number, number];
  radius?: number;
  length?: number;
};

/** A ring / field of hex-head bolts, instanced for cheap greeble density. */
export function BoltField({ positions, rotation, radius = 0.028, length = 0.05 }: BoltFieldProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const geometry = useMemo(() => new THREE.CylinderGeometry(radius, radius, length, 6), [radius, length]);
  const material = useMemo(() => boltMaterial(), []);

  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const dummy = new THREE.Object3D();
    positions.forEach((pos, i) => {
      dummy.position.set(...pos);
      if (rotation) dummy.rotation.set(...rotation);
      else dummy.rotation.set(Math.PI / 2, 0, 0);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
  }, [positions, rotation]);

  return (
    <instancedMesh
      ref={meshRef}
      args={[geometry, material, positions.length]}
      castShadow
      receiveShadow
    />
  );
}

export function circleOfBolts(count: number, radius: number, y = 0, axis: "y" | "x" | "z" = "y"): Array<[number, number, number]> {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2;
    const x = Math.cos(angle) * radius;
    const z = Math.sin(angle) * radius;
    if (axis === "y") return [x, y, z] as [number, number, number];
    if (axis === "x") return [y, x, z] as [number, number, number];
    return [x, z, y] as [number, number, number];
  });
}

type VentFieldProps = {
  rows: number;
  cols: number;
  cellSize: number;
  gap: number;
  center?: [number, number, number];
  plane?: "xy" | "xz";
};

/** Grid of cooling vent slots, instanced. */
export function VentField({ rows, cols, cellSize, gap, center = [0, 0, 0], plane = "xy" }: VentFieldProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const geometry = useMemo(() => new THREE.BoxGeometry(cellSize, cellSize * 3.2, 0.01), [cellSize]);
  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#000000",
        metalness: 0.1,
        roughness: 0.9,
      }),
    []
  );

  const count = rows * cols;

  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const dummy = new THREE.Object3D();
    let i = 0;
    const w = (cols - 1) * gap;
    const h = (rows - 1) * gap;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const x = c * gap - w / 2 + center[0];
        const y = r * gap - h / 2 + center[1];
        if (plane === "xy") {
          dummy.position.set(x, y, center[2]);
          dummy.rotation.set(0, 0, 0);
        } else {
          dummy.position.set(x, center[1], y);
          dummy.rotation.set(Math.PI / 2, 0, 0);
        }
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
        i++;
      }
    }
    mesh.instanceMatrix.needsUpdate = true;
  }, [rows, cols, gap, center, plane]);

  return <instancedMesh ref={meshRef} args={[geometry, material, count]} />;
}
