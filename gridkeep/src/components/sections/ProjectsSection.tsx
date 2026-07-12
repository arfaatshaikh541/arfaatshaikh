"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import type { ComponentType } from "react";
import PrototypeStage from "@/components/three/PrototypeStage";
import Reveal from "@/components/ui/Reveal";
import { PROJECTS } from "@/lib/projects-data";

const SoftwareRack = dynamic(() => import("@/components/three/prototypes/SoftwareRack"), { ssr: false });
const BusinessHub = dynamic(() => import("@/components/three/prototypes/BusinessHub"), { ssr: false });
const WebExperienceRig = dynamic(() => import("@/components/three/prototypes/WebExperienceRig"), { ssr: false });

const PROJECT_VISUALS: Record<string, { Prototype: ComponentType; cameraPosition: [number, number, number] }> = {
  rafana: { Prototype: SoftwareRack, cameraPosition: [1.7, 0.7, 2.3] },
  "ai-customer-engagement": { Prototype: BusinessHub, cameraPosition: [1.9, 1.3, 2.1] },
  "gridkeep-digital-experience": { Prototype: WebExperienceRig, cameraPosition: [1.7, 0.4, 2.5] },
};

export default function ProjectsSection() {
  return (
    <section
      id="projects"
      aria-labelledby="projects-heading"
      className="border-b border-gk-graphite bg-gk-black px-5 py-24 sm:px-8"
    >
      <div className="mx-auto max-w-[1600px]">
        <Reveal>
          <p className="gk-eyebrow">Selected Projects</p>
          <h2 id="projects-heading" className="font-display mt-4 max-w-2xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            Systems in <span className="gk-orange-text">production.</span>
          </h2>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-5 lg:grid-cols-3">
          {PROJECTS.map((project, i) => {
            const visual = PROJECT_VISUALS[project.slug];
            return (
              <Reveal key={project.slug} delay={i * 0.06}>
                <Link
                  href={`/projects/${project.slug}`}
                  className="gk-panel group flex h-full flex-col overflow-hidden border border-gk-steel transition-colors hover:border-gk-orange/60"
                >
                  <div className="relative h-48 border-b border-gk-steel bg-gk-black">
                    <PrototypeStage
                      title={project.prototypeLabel}
                      description={project.prototypeDescription}
                      className="h-full w-full"
                      cameraPosition={visual.cameraPosition}
                      fov={34}
                    >
                      <visual.Prototype />
                    </PrototypeStage>
                  </div>
                  <div className="flex flex-1 flex-col gap-3 p-6">
                    <span className="font-mono-tech text-[0.68rem] uppercase tracking-[0.14em] text-gk-orange">
                      {project.status}
                    </span>
                    <h3 className="font-display text-xl font-semibold text-gk-white">{project.name}</h3>
                    <p className="text-sm leading-relaxed text-gk-grey">{project.summary}</p>
                  </div>
                </Link>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
