"use client";

import { useRef } from "react";
import Link from "next/link";
import { ChapterScene } from "@/components/three/ChapterScene";
import { Reveal } from "@/components/ui/Reveal";
import { SectionLabel } from "@/components/ui/SectionLabel";
import type { Service } from "@/types";
import { cn } from "@/lib/utils";

interface ServiceChapterProps {
  service: Service;
  index: number;
}

export function ServiceChapter({ service, index }: ServiceChapterProps) {
  const sectionRef = useRef<HTMLElement | null>(null);
  const reversed = index % 2 === 1;

  return (
    <section
      ref={sectionRef}
      className="relative flex min-h-[130vh] flex-col border-t border-line"
      aria-labelledby={`chapter-${service.slug}`}
    >
      <div className="sticky top-16 h-[calc(100vh-4rem)] w-full overflow-hidden">
        <ChapterScene scene={service.scene} sectionRef={sectionRef} className="absolute inset-0" />

        <div
          className={cn(
            "relative z-10 mx-auto flex h-full max-w-[1600px] flex-col justify-center px-6 md:px-10",
            reversed ? "items-end text-right" : "items-start text-left"
          )}
        >
          <div className={cn("max-w-lg", reversed && "items-end")}>
            <Reveal>
              <SectionLabel index={String(index + 1).padStart(2, "0")} label={service.eyebrow} />
            </Reveal>
            <Reveal delay={0.08}>
              <h2 id={`chapter-${service.slug}`} className="mt-6 text-balance font-display text-4xl text-warm md:text-5xl">
                {service.name}
              </h2>
            </Reveal>
            <Reveal delay={0.14}>
              <p className="mt-5 text-balance text-muted">{service.summary}</p>
            </Reveal>
            <Reveal delay={0.2}>
              <ul className={cn("mt-6 flex flex-col gap-2", reversed && "items-end")}>
                {service.capabilities.slice(0, 3).map((capability) => (
                  <li key={capability} className="font-mono text-xs uppercase tracking-widest2 text-muted">
                    {capability}
                  </li>
                ))}
              </ul>
            </Reveal>
            <Reveal delay={0.26}>
              <Link
                href={`/services/${service.slug}`}
                className="mt-8 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest2 text-orange hover:text-orange-bright"
              >
                View {service.shortName} →
              </Link>
            </Reveal>
          </div>
        </div>
      </div>
    </section>
  );
}
