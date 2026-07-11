"use client";

import { useRef, type MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import "@/components/three/materials";
import { usePointerParallax } from "@/components/three/usePointerParallax";
import { useOrbitingInstances } from "@/components/three/useOrbitingInstances";
import { useIsMobile, usePrefersReducedMotion, particleCount } from "@/lib/performance";

interface CoreSceneProps {
  progressRef?: MutableRefObject<number>;
  dollyCamera?: boolean;
}

const DEBRIS_DUMMY = new THREE.Object3D();

export function CoreScene({ progressRef, dollyCamera = false }: CoreSceneProps) {
  const outerShell = useRef<THREE.Mesh>(null);
  const midShell = useRef<THREE.Mesh>(null);
  const innerCore = useRef<THREE.Mesh>(null);
  const group = useRef<THREE.Group>(null);
  const debrisMesh = useRef<THREE.InstancedMesh>(null);
  const outerMat = useRef<any>(null);
  const midMat = useRef<any>(null);
  const coreMat = useRef<any>(null);

  const pointer = usePointerParallax();
  const isMobile = useIsMobile();
  const reducedMotion = usePrefersReducedMotion();
  const debrisCount = particleCount(isMobile ? 24 : 48, isMobile, reducedMotion);
  const debris = useOrbitingInstances(debrisCount, [2.6, 4.4]);
  const { camera } = useThree();

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const progress = progressRef?.current ?? 0;

    if (outerShell.current) {
      outerShell.current.rotation.y += delta * 0.06;
      outerShell.current.rotation.x = Math.sin(t * 0.08) * 0.08;
      const openScale = 1 + progress * 0.6;
      outerShell.current.scale.setScalar(openScale);
    }
    if (midShell.current) {
      midShell.current.rotation.y -= delta * 0.12;
      midShell.current.rotation.z += delta * 0.05;
    }
    if (innerCore.current) {
      const breathe = 1 + Math.sin(t * 0.9) * 0.04 + progress * 0.15;
      innerCore.current.scale.setScalar(breathe);
    }

    if (outerMat.current) {
      outerMat.current.uTime = t;
      outerMat.current.uActivation = 0.45 + progress * 0.5 + Math.sin(t * 0.4) * 0.05;
    }
    if (midMat.current) {
      midMat.current.uTime = t;
      midMat.current.uActivation = 0.6 + progress * 0.4;
    }
    if (coreMat.current) {
      coreMat.current.uTime = t;
      coreMat.current.uActivation = 0.8 + progress * 0.4;
    }

    if (group.current && !reducedMotion) {
      group.current.rotation.y = THREE.MathUtils.lerp(
        group.current.rotation.y,
        pointer.current.x * 0.18,
        0.03
      );
      group.current.rotation.x = THREE.MathUtils.lerp(
        group.current.rotation.x,
        pointer.current.y * 0.12,
        0.03
      );
    }

    if (debrisMesh.current) {
      debris.forEach((datum, index) => {
        const angle = t * datum.speed + datum.phase + progress * 2.4;
        const radius = datum.radius + progress * 1.4;
        DEBRIS_DUMMY.position.set(
          Math.cos(angle) * radius,
          datum.y + Math.sin(t * 0.3 + datum.phase) * 0.3,
          Math.sin(angle) * radius
        );
        DEBRIS_DUMMY.rotation.set(angle, angle * 0.6, 0);
        DEBRIS_DUMMY.scale.setScalar(datum.scale);
        DEBRIS_DUMMY.updateMatrix();
        debrisMesh.current!.setMatrixAt(index, DEBRIS_DUMMY.matrix);
      });
      debrisMesh.current.instanceMatrix.needsUpdate = true;
    }

    if (dollyCamera) {
      const targetZ = 9 - progress * 4.2;
      camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZ, 0.04);
      camera.lookAt(0, 0, 0);
    }
  });

  return (
    <group ref={group}>
      <mesh ref={outerShell}>
        <icosahedronGeometry args={[2.6, 1]} />
        <energyMaterial
          ref={outerMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#7A2200"
          uColorBright="#FF7A1A"
          uFresnelPower={2.6}
          uNoiseScale={0.5}
          uIntensity={0.9}
        />
      </mesh>

      <mesh ref={midShell} rotation={[0.5, 0, 0.3]}>
        <torusGeometry args={[1.9, 0.05, 16, 96]} />
        <energyMaterial
          ref={midMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#C84400"
          uColorBright="#FF9A3D"
          uFresnelPower={1.4}
          uNoiseScale={1.2}
          uIntensity={1.3}
        />
      </mesh>
      <mesh rotation={[-0.4, 0.6, 0]}>
        <torusGeometry args={[1.5, 0.03, 16, 96]} />
        <energyMaterial
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#7A2200"
          uColorBright="#FF5A00"
          uFresnelPower={1.8}
          uNoiseScale={1.4}
          uIntensity={1.1}
        />
      </mesh>

      <mesh ref={innerCore}>
        <sphereGeometry args={[0.85, 48, 48]} />
        <energyMaterial
          ref={coreMat}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uColorDeep="#FF5A00"
          uColorBright="#FF9A3D"
          uFresnelPower={0.9}
          uNoiseScale={2.2}
          uIntensity={1.6}
        />
      </mesh>

      <instancedMesh ref={debrisMesh} args={[undefined, undefined, debrisCount]}>
        <tetrahedronGeometry args={[0.09, 0]} />
        <meshStandardMaterial
          color="#0b0b0b"
          metalness={0.85}
          roughness={0.3}
          emissive="#C84400"
          emissiveIntensity={0.5}
        />
      </instancedMesh>
    </group>
  );
}
