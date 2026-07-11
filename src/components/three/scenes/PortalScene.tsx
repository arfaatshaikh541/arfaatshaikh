"use client";

import { useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { usePointerParallax } from "@/components/three/usePointerParallax";
import { usePrefersReducedMotion } from "@/lib/performance";

interface PortalSceneProps {
  progressRef?: MutableRefObject<number>;
}

export function PortalScene({ progressRef }: PortalSceneProps) {
  const portalMat = useRef<any>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const ringMat = useRef<any>(null);
  const group = useRef<THREE.Group>(null);
  const pointer = usePointerParallax();
  const reducedMotion = usePrefersReducedMotion();

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (portalMat.current) {
      portalMat.current.uTime = t;
      portalMat.current.uOpen = 0.18 + progress * 0.82;
      portalMat.current.uPointer.set(pointer.current.x, pointer.current.y);
    }
    if (ringRef.current) ringRef.current.rotation.z += 0.0025;
    if (ringMat.current) ringMat.current.uTime = t;

    if (group.current && !reducedMotion) {
      group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, pointer.current.x * 0.08, 0.04);
    }
  });

  return (
    <group ref={group}>
      <mesh>
        <circleGeometry args={[2.4, 96]} />
        <portalMaterial ref={portalMat} transparent depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      <mesh ref={ringRef}>
        <torusGeometry args={[2.42, 0.035, 16, 128]} />
        <energyMaterial
          ref={ringMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#C84400"
          uColorBright="#FF9A3D"
          uFresnelPower={0.8}
          uNoiseScale={1.2}
          uIntensity={1.4}
        />
      </mesh>
    </group>
  );
}
