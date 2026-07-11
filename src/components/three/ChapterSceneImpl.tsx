"use client";

import { useRef, type RefObject } from "react";
import { SceneCanvas } from "./SceneCanvas";
import { useScrollProgress } from "./useScrollProgress";
import { SCENE_CAMERA, SCENE_REGISTRY } from "./sceneRegistry";
import type { SceneId } from "@/types";

interface ChapterSceneProps {
  scene: SceneId;
  sectionRef?: RefObject<HTMLElement | null>;
  className?: string;
  postFX?: boolean;
  interactive?: boolean;
  idleProgress?: number;
}

export function ChapterScene({
  scene,
  sectionRef,
  className,
  postFX = true,
  interactive = true,
  idleProgress = 0.55,
}: ChapterSceneProps) {
  const fallbackRef = useRef<HTMLElement | null>(null);
  const progressRef = useScrollProgress(sectionRef ?? fallbackRef);
  const SceneComponent = SCENE_REGISTRY[scene];

  if (!sectionRef) {
    progressRef.current = idleProgress;
  }

  return (
    <SceneCanvas
      scene={scene}
      cameraPosition={SCENE_CAMERA[scene]}
      postFX={postFX}
      interactive={interactive}
      className={className}
    >
      <SceneComponent progressRef={progressRef} />
    </SceneCanvas>
  );
}
