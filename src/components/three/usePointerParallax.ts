"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export function usePointerParallax() {
  const pointer = useRef(new THREE.Vector2(0, 0));

  useEffect(() => {
    function handlePointerMove(event: PointerEvent) {
      pointer.current.x = (event.clientX / window.innerWidth) * 2 - 1;
      pointer.current.y = -((event.clientY / window.innerHeight) * 2 - 1);
    }
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    return () => window.removeEventListener("pointermove", handlePointerMove);
  }, []);

  return pointer;
}
