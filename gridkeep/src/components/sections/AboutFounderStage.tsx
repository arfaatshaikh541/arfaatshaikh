"use client";

import dynamic from "next/dynamic";
import PrototypeStage from "@/components/three/PrototypeStage";
import { useScrollProgress } from "@/hooks/useScrollProgress";

const FounderConsole = dynamic(() => import("@/components/three/prototypes/FounderConsole"), { ssr: false });

export default function AboutFounderStage() {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top 70%",
    end: "bottom 30%",
    scrub: 0.8,
  });

  return (
    <div ref={sectionRef} className="relative h-[380px] sm:h-[480px]">
      <PrototypeStage
        title="Founder Command Module"
        description="A black command console beneath a circular orange system frame holding an abstract signature mark and system architecture panels — a founder identity represented through typography and system diagrams, never a photograph or human likeness."
        className="h-full w-full"
        cameraPosition={[0.4, 0.3, 3.4]}
        fov={38}
      >
        <FounderConsole progressRef={progressRef} />
      </PrototypeStage>
    </div>
  );
}
