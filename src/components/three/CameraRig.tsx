"use client";

import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { sceneState } from "@/lib/sceneStore";

// iOS 13+ Safari gates DeviceOrientationEvent behind an explicit permission
// prompt that can only be requested from a user gesture — this type isn't
// part of the standard DOM lib, so it's declared locally.
interface DeviceOrientationEventWithPermission {
  requestPermission?: () => Promise<"granted" | "denied">;
}

export function CameraRig() {
  const { camera } = useThree();
  const target = useRef(new THREE.Vector3(0, 0, 0));
  const pointer = useRef({ x: 0, y: 0 });
  const enablePointerParallax = useRef(true);
  const enableGyro = useRef(false);
  const gyroBase = useRef<{ beta: number; gamma: number } | null>(null);

  useEffect(() => {
    const isCoarse = window.matchMedia("(pointer: coarse)").matches;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    enablePointerParallax.current = !isCoarse && !reducedMotion;
    enableGyro.current = isCoarse && !reducedMotion;

    const onMove = (event: PointerEvent) => {
      if (!enablePointerParallax.current) return;
      pointer.current.x = (event.clientX / window.innerWidth - 0.5) * 2;
      pointer.current.y = (event.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const onOrientation = (event: DeviceOrientationEvent) => {
      if (!enableGyro.current) return;
      const beta = event.beta ?? 0;
      const gamma = event.gamma ?? 0;
      // Calibrate against the phone's initial resting angle so this reads
      // as a tilt *from* however the user happens to be holding it, not an
      // absolute compass-style orientation.
      if (!gyroBase.current) {
        gyroBase.current = { beta, gamma };
      }
      const dBeta = beta - gyroBase.current.beta;
      const dGamma = gamma - gyroBase.current.gamma;
      pointer.current.x = THREE.MathUtils.clamp(dGamma / 30, -1, 1);
      pointer.current.y = THREE.MathUtils.clamp(dBeta / 30, -1, 1);
    };

    let removeGyroListener: (() => void) | null = null;
    let removeGestureListener: (() => void) | null = null;

    if (enableGyro.current) {
      const DOE = DeviceOrientationEvent as unknown as DeviceOrientationEventWithPermission;

      if (typeof DOE.requestPermission === "function") {
        // Can only be requested inside a user gesture, so wait for the
        // visitor's first tap anywhere on the page before asking.
        const requestOnGesture = () => {
          DOE.requestPermission?.()
            .then((state) => {
              if (state === "granted") {
                window.addEventListener("deviceorientation", onOrientation);
                removeGyroListener = () =>
                  window.removeEventListener("deviceorientation", onOrientation);
              }
            })
            .catch(() => {});
        };
        window.addEventListener("touchend", requestOnGesture, { once: true, passive: true });
        removeGestureListener = () => window.removeEventListener("touchend", requestOnGesture);
      } else {
        window.addEventListener("deviceorientation", onOrientation);
        removeGyroListener = () => window.removeEventListener("deviceorientation", onOrientation);
      }
    }

    return () => {
      window.removeEventListener("pointermove", onMove);
      removeGyroListener?.();
      removeGestureListener?.();
    };
  }, []);

  useFrame(() => {
    sceneState.parallaxX = THREE.MathUtils.lerp(sceneState.parallaxX, pointer.current.x * 0.25, 0.04);
    sceneState.parallaxY = THREE.MathUtils.lerp(sceneState.parallaxY, -pointer.current.y * 0.15, 0.04);

    const desiredX = sceneState.camX + sceneState.parallaxX;
    const desiredY = sceneState.camY + sceneState.parallaxY;
    const desiredZ = sceneState.camZ + sceneState.pulseZOffset;

    camera.position.x = THREE.MathUtils.lerp(camera.position.x, desiredX, 0.05);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, desiredY, 0.05);
    camera.position.z = THREE.MathUtils.lerp(camera.position.z, desiredZ, 0.08);

    target.current.set(
      THREE.MathUtils.lerp(target.current.x, sceneState.targetX, 0.06),
      THREE.MathUtils.lerp(target.current.y, sceneState.targetY, 0.06),
      THREE.MathUtils.lerp(target.current.z, sceneState.targetZ, 0.06)
    );
    camera.lookAt(target.current);
  });

  return null;
}
