"use client";

import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

export function CameraRig() {
  const { camera } = useThree();
  const target = useRef(new THREE.Vector3(0, 0, 0));
  const pointer = useRef({ x: 0, y: 0 });
  const enableParallax = useRef(true);

  useEffect(() => {
    const isCoarse = window.matchMedia("(pointer: coarse)").matches;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    enableParallax.current = !isCoarse && !reducedMotion;

    const onMove = (event: PointerEvent) => {
      if (!enableParallax.current) return;
      pointer.current.x = (event.clientX / window.innerWidth - 0.5) * 2;
      pointer.current.y = (event.clientY / window.innerHeight - 0.5) * 2;
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  useFrame(() => {
    sceneState.parallaxX = THREE.MathUtils.lerp(sceneState.parallaxX, pointer.current.x * 0.25, 0.04);
    sceneState.parallaxY = THREE.MathUtils.lerp(sceneState.parallaxY, -pointer.current.y * 0.15, 0.04);

    const desiredX = sceneState.camX + sceneState.parallaxX;
    const desiredY = sceneState.camY + sceneState.parallaxY;
    const desiredZ = sceneState.camZ;

    camera.position.x = THREE.MathUtils.lerp(camera.position.x, desiredX, 0.05);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, desiredY, 0.05);
    camera.position.z = THREE.MathUtils.lerp(camera.position.z, desiredZ, 0.05);

    target.current.set(
      THREE.MathUtils.lerp(target.current.x, sceneState.targetX, 0.06),
      THREE.MathUtils.lerp(target.current.y, sceneState.targetY, 0.06),
      THREE.MathUtils.lerp(target.current.z, sceneState.targetZ, 0.06)
    );
    camera.lookAt(target.current);
  });

  return null;
}
