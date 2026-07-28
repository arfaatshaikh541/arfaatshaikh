"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

const ARC_COUNT = 6;
const SEGMENT_ITERATIONS = 4;
const REGEN_INTERVAL = 0.09; // seconds between reshuffling arc paths — gives a flicker, not a smooth glide

function randomDirection(): THREE.Vector3 {
  const v = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1);
  return v.lengthSq() > 0.0001 ? v.normalize() : new THREE.Vector3(0, 1, 0);
}

// Classic recursive midpoint-displacement lightning generator: repeatedly
// subdivides the segment and nudges each new midpoint sideways by a
// shrinking random amount, so the path looks jagged near the ends and
// coheres toward the endpoints.
function displaceMidpoints(points: THREE.Vector3[], wildness: number): THREE.Vector3[] {
  const next: THREE.Vector3[] = [points[0]];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    const mid = a.clone().lerp(b, 0.5);
    const segLen = a.distanceTo(b);
    mid.add(randomDirection().multiplyScalar(segLen * wildness * (0.4 + Math.random() * 0.8)));
    next.push(mid, b);
  }
  return next;
}

function generateArcPositions(start: THREE.Vector3, end: THREE.Vector3): Float32Array {
  let points = [start, end];
  let wildness = 0.55;
  for (let i = 0; i < SEGMENT_ITERATIONS; i++) {
    points = displaceMidpoints(points, wildness);
    wildness *= 0.55;
  }
  const array = new Float32Array(points.length * 3);
  points.forEach((p, i) => {
    array[i * 3] = p.x;
    array[i * 3 + 1] = p.y;
    array[i * 3 + 2] = p.z;
  });
  return array;
}

interface ArcSlot {
  line: THREE.Line;
  start: THREE.Vector3;
  end: THREE.Vector3;
}

function randomStart(): THREE.Vector3 {
  return randomDirection().multiplyScalar(1.15 + Math.random() * 0.15);
}

function randomEnd(): THREE.Vector3 {
  return randomDirection().multiplyScalar(2.0 + Math.random() * 0.5);
}

export function ElectricArcs() {
  const timerRef = useRef(0);

  const material = useMemo(
    () =>
      new THREE.LineBasicMaterial({
        color: "#ff3b20",
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    []
  );

  const arcs = useMemo(() => {
    const list: ArcSlot[] = [];
    for (let i = 0; i < ARC_COUNT; i++) {
      const start = randomStart();
      const end = randomEnd();
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(generateArcPositions(start, end), 3));
      const line = new THREE.Line(geometry, material);
      line.frustumCulled = false;
      list.push({ line, start, end });
    }
    return list;
  }, [material]);

  useEffect(() => {
    return () => {
      arcs.forEach((arc) => arc.line.geometry.dispose());
      material.dispose();
    };
  }, [arcs, material]);

  useFrame((_, delta) => {
    const targetOpacity = THREE.MathUtils.clamp(
      0.12 +
        sceneState.turbulence * 0.25 +
        sceneState.hoverIntensity * 0.5 +
        sceneState.pulseStrength * 0.8,
      0,
      1
    );
    material.opacity = THREE.MathUtils.lerp(material.opacity, targetOpacity, 0.15);

    timerRef.current += delta;
    if (timerRef.current < REGEN_INTERVAL) return;
    timerRef.current = 0;

    arcs.forEach((arc) => {
      // Occasionally jump to a new start/end so arcs strike different spots.
      if (Math.random() < 0.35) {
        arc.start.copy(randomStart());
        arc.end.copy(randomEnd());
      }
      const positions = generateArcPositions(arc.start, arc.end);
      const attr = arc.line.geometry.getAttribute("position") as THREE.BufferAttribute;
      if (attr.array.length === positions.length) {
        (attr.array as Float32Array).set(positions);
        attr.needsUpdate = true;
      } else {
        arc.line.geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      }
    });
  });

  return (
    <group>
      {arcs.map((arc, i) => (
        <primitive key={i} object={arc.line} />
      ))}
    </group>
  );
}
