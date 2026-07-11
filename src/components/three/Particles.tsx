"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

function useSoftDotTexture(): THREE.Texture {
  return useMemo(() => {
    const size = 64;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      const gradient = ctx.createRadialGradient(
        size / 2,
        size / 2,
        0,
        size / 2,
        size / 2,
        size / 2
      );
      gradient.addColorStop(0, "rgba(255,255,255,1)");
      gradient.addColorStop(0.4, "rgba(255,255,255,0.6)");
      gradient.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, size, size);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    return texture;
  }, []);
}

interface FieldProps {
  count: number;
  texture: THREE.Texture;
  color: string;
  size: number;
  speed: number;
  spread: number;
  opacityScale: number;
  additive?: boolean;
}

function ParticleField({ count, texture, color, size, speed, spread, opacityScale, additive }: FieldProps) {
  const pointsRef = useRef<THREE.Points>(null);
  const materialRef = useRef<THREE.PointsMaterial>(null);

  const [positions, seeds] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const seed = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const radius = 1.8 + Math.random() * spread;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      pos[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = radius * Math.cos(phi) * 0.6;
      pos[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
      seed[i] = Math.random() * 100;
    }
    return [pos, seed];
  }, [count, spread]);

  useFrame((state, delta) => {
    const points = pointsRef.current;
    const material = materialRef.current;
    if (!points || !material) return;

    const geometry = points.geometry;
    const posAttr = geometry.attributes.position as THREE.BufferAttribute;
    const array = posAttr.array as Float32Array;
    const t = state.clock.elapsedTime;

    for (let i = 0; i < count; i++) {
      const idx = i * 3;
      array[idx + 1] += delta * speed * (0.5 + (seeds[i] % 3) * 0.2);
      array[idx] += Math.sin(t * 0.5 + seeds[i]) * delta * 0.05;

      if (array[idx + 1] > 3.4) {
        const radius = 1.8 + Math.random() * spread;
        const theta = Math.random() * Math.PI * 2;
        array[idx] = radius * Math.cos(theta) * 0.6;
        array[idx + 1] = -2.2;
        array[idx + 2] = radius * Math.sin(theta) * 0.6;
      }
    }
    posAttr.needsUpdate = true;

    material.opacity = Math.min(0.9, sceneState.particleMix * opacityScale);
    points.visible = material.opacity > 0.01;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        ref={materialRef}
        map={texture}
        size={size}
        color={color}
        transparent
        opacity={0}
        depthWrite={false}
        sizeAttenuation
        blending={additive ? THREE.AdditiveBlending : THREE.NormalBlending}
      />
    </points>
  );
}

export function Particles() {
  const texture = useSoftDotTexture();
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    setIsMobile(window.innerWidth < 768);
  }, []);

  const smokeCount = isMobile ? 60 : 160;
  const emberCount = isMobile ? 30 : 90;

  return (
    <>
      <ParticleField
        count={smokeCount}
        texture={texture}
        color="#3a1210"
        size={0.55}
        speed={0.18}
        spread={1.1}
        opacityScale={0.5}
      />
      <ParticleField
        count={emberCount}
        texture={texture}
        color="#ff5a2e"
        size={0.045}
        speed={0.55}
        spread={0.7}
        opacityScale={1}
        additive
      />
    </>
  );
}
