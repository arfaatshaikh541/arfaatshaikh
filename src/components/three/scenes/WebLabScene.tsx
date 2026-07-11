"use client";

import { useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { usePointerParallax } from "@/components/three/usePointerParallax";
import { usePrefersReducedMotion } from "@/lib/performance";

interface WebLabSceneProps {
  progressRef?: MutableRefObject<number>;
}

const PANEL_COUNT = 7;

export function WebLabScene({ progressRef }: WebLabSceneProps) {
  const group = useRef<THREE.Group>(null);
  const panelRefs = useRef<(THREE.Mesh | null)[]>([]);
  const panelMats = useRef<any[]>([]);
  const pointer = usePointerParallax();
  const reducedMotion = usePrefersReducedMotion();

  const panels = useMemo(() => {
    const cols = 3;
    return Array.from({ length: PANEL_COUNT }, (_, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const target = new THREE.Vector3((col - 1) * 1.7, (row - 1) * 1.3, i === 0 ? 0.6 : 0);
      const dispersed = new THREE.Vector3(
        (Math.random() - 0.5) * 7,
        (Math.random() - 0.5) * 4,
        (Math.random() - 0.5) * 4 - 1.5
      );
      return {
        target,
        dispersed,
        width: i === 0 ? 1.7 : 1.2 + Math.random() * 0.3,
        height: i === 0 ? 1.1 : 0.7 + Math.random() * 0.2,
        hero: i === 0,
      };
    });
  }, []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (group.current && !reducedMotion) {
      group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, pointer.current.x * 0.12, 0.04);
      group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, pointer.current.y * 0.08, 0.04);
    }

    panels.forEach((panel, index) => {
      const mesh = panelRefs.current[index];
      if (!mesh) return;
      const eased = THREE.MathUtils.smoothstep(progress, 0, 1);
      mesh.position.lerpVectors(panel.dispersed, panel.target, eased);
      mesh.position.y += Math.sin(t * 0.4 + index) * 0.04;
      mesh.rotation.y = (1 - eased) * 0.8;

      if (panel.hero) {
        const scale = 1 + eased * 1.6;
        mesh.scale.setScalar(scale);
        mesh.position.z = THREE.MathUtils.lerp(0.6, 2.4, eased);
      }

      const mat = panelMats.current[index];
      if (mat) {
        mat.uTime = t;
        mat.uActivation = 0.4 + eased * 0.6;
      }
    });
  });

  return (
    <group ref={group}>
      {panels.map((panel, index) => (
        <mesh
          key={index}
          ref={(el) => {
            panelRefs.current[index] = el;
          }}
        >
          <planeGeometry args={[panel.width, panel.height]} />
          <energyMaterial
            ref={(el: any) => {
              panelMats.current[index] = el;
            }}
            transparent
            depthWrite={false}
            side={THREE.DoubleSide}
            blending={THREE.AdditiveBlending}
            uColorDeep="#2a1206"
            uColorBright="#FF7A1A"
            uFresnelPower={3.2}
            uNoiseScale={0.6}
            uIntensity={0.55}
          />
        </mesh>
      ))}
    </group>
  );
}
