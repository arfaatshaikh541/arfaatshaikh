"use client";

import { useRef } from "react";
import Link from "next/link";
import { ChapterScene } from "@/components/three/ChapterScene";
import { Reveal } from "@/components/ui/Reveal";
import { SectionLabel } from "@/components/ui/SectionLabel";

export function EcosystemSection() {
  const sectionRef = useRef<HTMLElement | null>(null);

  return (
    <section
      ref={sectionRef}
      className="relative flex min-h-[140vh] flex-col border-t border-line"
      aria-labelledby="ecosystem-heading"
    >
      <div className="sticky top-0 h-screen w-full overflow-hidden">
        <ChapterScene scene="command" sectionRef={sectionRef} className="absolute inset-0" />

        <div className="relative z-10 mx-auto flex h-full max-w-[1600px] flex-col items-center justify-center px-6 text-center md:px-10">
          <Reveal>
            <SectionLabel index="13" label="The GRIDKEEP system" />
          </Reveal>
          <Reveal delay={0.08}>
            <h2 id="ecosystem-heading" className="mt-6 max-w-3xl text-balance font-display text-4xl text-warm md:text-5xl">
              Every system connects back to one architecture.
            </h2>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-6 max-w-xl text-balance text-muted">
              AI, automation, software, security, and infrastructure are not separate
              disciplines at GRIDKEEP. They are modules of one connected operating system,
              engineered to work together from the start.
            </p>
          </Reveal>
          <Reveal delay={0.24}>
            <Link
              href="/gridkeep-system"
              className="mt-8 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest2 text-orange hover:text-orange-bright"
            >
              Explore the GRIDKEEP System →
            </Link>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
