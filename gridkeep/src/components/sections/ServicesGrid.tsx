"use client";

import dynamic from "next/dynamic";
import ServiceCard from "./ServiceCard";
import Reveal from "@/components/ui/Reveal";
import { SERVICES } from "@/lib/services-data";

const AIInferenceNode = dynamic(() => import("@/components/three/prototypes/AIInferenceNode"), { ssr: false });
const AutomationCell = dynamic(() => import("@/components/three/prototypes/AutomationCell"), { ssr: false });
const SoftwareRack = dynamic(() => import("@/components/three/prototypes/SoftwareRack"), { ssr: false });
const CyberVault = dynamic(() => import("@/components/three/prototypes/CyberVault"), { ssr: false });
const CloudArray = dynamic(() => import("@/components/three/prototypes/CloudArray"), { ssr: false });
const BusinessHub = dynamic(() => import("@/components/three/prototypes/BusinessHub"), { ssr: false });

const CARD_CONFIG = [
  { slug: "ai-agents", Prototype: AIInferenceNode, cameraPosition: [1.9, 1, 2.4] as [number, number, number] },
  { slug: "automation", Prototype: AutomationCell, cameraPosition: [2.6, 1.2, 3] as [number, number, number] },
  { slug: "software-saas", Prototype: SoftwareRack, cameraPosition: [1.6, 0.6, 2.2] as [number, number, number] },
  { slug: "cybersecurity", Prototype: CyberVault, cameraPosition: [1.6, 0.8, 2.2] as [number, number, number] },
  { slug: "cloud-devops", Prototype: CloudArray, cameraPosition: [1.6, 0.6, 2.2] as [number, number, number] },
  { slug: "business-systems", Prototype: BusinessHub, cameraPosition: [1.8, 1.3, 2] as [number, number, number] },
];

export default function ServicesGrid() {
  return (
    <section
      id="services"
      aria-labelledby="services-heading"
      className="border-b border-gk-graphite bg-gk-black px-5 py-24 sm:px-8"
    >
      <div className="mx-auto max-w-[1600px]">
        <Reveal>
          <p className="gk-eyebrow">Capability Grid</p>
          <h2 id="services-heading" className="font-display mt-4 max-w-2xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            Six systems. <span className="gk-orange-text">One operating standard.</span>
          </h2>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {CARD_CONFIG.map((card, i) => {
            const service = SERVICES.find((s) => s.slug === card.slug)!;
            return (
              <Reveal key={card.slug} delay={i * 0.05}>
                <ServiceCard service={service} Prototype={card.Prototype} cameraPosition={card.cameraPosition} />
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
