"use client";

import { useRef } from "react";
import { ChapterScene } from "@/components/three/ChapterScene";
import { ButtonLink } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";

export function HeroSection() {
  const sectionRef = useRef<HTMLElement | null>(null);

  return (
    <section
      ref={sectionRef}
      className="relative flex h-[160vh] flex-col"
      aria-label="GRIDKEEP introduction"
    >
      <div className="sticky top-0 h-screen w-full overflow-hidden">
        <ChapterScene scene="core" sectionRef={sectionRef} className="absolute inset-0" />

        <div className="grid-overlay pointer-events-none absolute inset-0 opacity-[0.07]" />

        <div className="relative z-10 mx-auto flex h-full max-w-[1600px] flex-col justify-center px-6 md:px-10">
          <Reveal>
            <p className="font-mono text-xs uppercase tracking-widest2 text-orange">
              Founder-led technology system
            </p>
          </Reveal>
          <Reveal delay={0.08}>
            <h1 className="mt-6 max-w-3xl text-balance font-display text-5xl leading-[1.05] text-warm sm:text-6xl md:text-7xl">
              We build the systems
              <br /> behind the business.
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-6 max-w-xl text-balance text-base text-muted md:text-lg">
              GRIDKEEP designs and engineers AI, automation, software, cybersecurity, cloud
              infrastructure, and immersive digital experiences for businesses that need more
              than disconnected tools.
            </p>
          </Reveal>
          <Reveal delay={0.24}>
            <div className="mt-10 flex flex-wrap gap-4">
              <ButtonLink href="/contact" variant="primary">
                Enter the system
              </ButtonLink>
              <ButtonLink href="/services" variant="secondary">
                Explore capabilities
              </ButtonLink>
            </div>
          </Reveal>
        </div>

        <div className="absolute bottom-8 left-1/2 z-10 -translate-x-1/2 font-mono text-[10px] uppercase tracking-widest2 text-muted">
          Scroll to activate the system
        </div>
      </div>
    </section>
  );
}
