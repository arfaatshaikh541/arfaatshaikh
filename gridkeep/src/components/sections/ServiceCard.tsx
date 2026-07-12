"use client";

import { useState, type ComponentType } from "react";
import Link from "next/link";
import PrototypeStage from "@/components/three/PrototypeStage";
import type { ServiceDefinition } from "@/lib/services-data";

type PrototypeProps = { hover?: number };

type Props = {
  service: ServiceDefinition;
  Prototype: ComponentType<PrototypeProps>;
  cameraPosition?: [number, number, number];
};

export default function ServiceCard({ service, Prototype, cameraPosition = [2.2, 1.3, 2.6] }: Props) {
  const [hovered, setHovered] = useState(false);

  return (
    <Link
      href={`/services/${service.slug}`}
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
      className="gk-panel group relative flex flex-col overflow-hidden border border-gk-steel transition-colors hover:border-gk-orange/60"
    >
      <div className="relative h-52 border-b border-gk-steel bg-gk-black sm:h-60">
        <PrototypeStage
          title={service.prototypeName}
          description={service.heroDescription}
          className="h-full w-full"
          cameraPosition={cameraPosition}
          fov={34}
        >
          <Prototype hover={hovered ? 1 : 0} />
        </PrototypeStage>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-6">
        <span className="gk-eyebrow">{service.index}</span>
        <h3 className="font-display text-xl font-semibold text-gk-white">{service.name}</h3>
        <p className="text-sm leading-relaxed text-gk-grey">{service.tagline}</p>
        <span className="mt-auto flex items-center gap-2 pt-3 font-mono-tech text-xs uppercase tracking-[0.14em] text-gk-orange">
          View System
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            className="transition-transform group-hover:translate-x-1"
            aria-hidden="true"
          >
            <path d="M1 7H13M13 7L7.5 1.5M13 7L7.5 12.5" stroke="currentColor" strokeWidth="1.4" />
          </svg>
        </span>
      </div>
    </Link>
  );
}
