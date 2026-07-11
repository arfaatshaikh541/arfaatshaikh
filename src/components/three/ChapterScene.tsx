"use client";

import dynamic from "next/dynamic";
import type { SceneId } from "@/types";
import { ScenePoster } from "./ScenePoster";
import { cn } from "@/lib/utils";

// React Three Fiber's reconciler cannot be server-rendered safely inside
// Next.js's App Router prerendering pass, so the real scene is loaded
// client-only. All SEO-relevant content lives outside this component in
// plain semantic HTML, so nothing meaningful is lost while it loads.
const LazyChapterScene = dynamic(
  () => import("./ChapterSceneImpl").then((mod) => mod.ChapterScene),
  {
    ssr: false,
    loading: () => null,
  }
);

interface ChapterSceneProps {
  scene: SceneId;
  sectionRef?: React.RefObject<HTMLElement | null>;
  className?: string;
  postFX?: boolean;
  interactive?: boolean;
  idleProgress?: number;
}

export function ChapterScene(props: ChapterSceneProps) {
  return (
    <div className={cn("relative h-full w-full overflow-hidden bg-black", props.className)}>
      <ScenePoster scene={props.scene} />
      <LazyChapterScene {...props} className="absolute inset-0" />
    </div>
  );
}
