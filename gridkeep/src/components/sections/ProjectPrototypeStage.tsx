"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import PrototypeStage from "@/components/three/PrototypeStage";
import type { ProjectSlug } from "@/lib/projects-data";

const SoftwareRack = dynamic(() => import("@/components/three/prototypes/SoftwareRack"), { ssr: false });
const BusinessHub = dynamic(() => import("@/components/three/prototypes/BusinessHub"), { ssr: false });
const WebExperienceRig = dynamic(() => import("@/components/three/prototypes/WebExperienceRig"), { ssr: false });

const VISUALS: Record<ProjectSlug, { Component: ComponentType; cameraPosition: [number, number, number] }> = {
  rafana: { Component: SoftwareRack, cameraPosition: [1.9, 0.7, 2.5] },
  "ai-customer-engagement": { Component: BusinessHub, cameraPosition: [2.1, 1.4, 2.3] },
  "gridkeep-digital-experience": { Component: WebExperienceRig, cameraPosition: [1.9, 0.4, 2.7] },
};

export default function ProjectPrototypeStage({
  slug,
  title,
  description,
}: {
  slug: ProjectSlug;
  title: string;
  description: string;
}) {
  const visual = VISUALS[slug];
  return (
    <div className="relative h-[360px] sm:h-[460px]">
      <PrototypeStage
        title={title}
        description={description}
        className="h-full w-full"
        cameraPosition={visual.cameraPosition}
        fov={36}
      >
        <visual.Component />
      </PrototypeStage>
    </div>
  );
}
