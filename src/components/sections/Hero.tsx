"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { LinkButton } from "@/components/ui/Button";
import SceneCanvas from "@/components/three/SceneCanvas";
import { gsap, ScrollTrigger, registerGsap } from "@/lib/gsap";
import { useReducedMotion } from "@/lib/useReducedMotion";

const HeroReactorScene = dynamic(() => import("@/components/three/HeroReactorScene"), { ssr: false });

export default function Hero() {
  const sectionRef = useRef<HTMLElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const progressRef = useRef(0);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    registerGsap();
    const ctx = gsap.context(() => {
      gsap.fromTo(
        ".hero-reveal",
        { autoAlpha: 0, y: 24 },
        { autoAlpha: 1, y: 0, duration: 0.9, ease: "power3.out", stagger: 0.08, delay: 0.15 }
      );

      if (sectionRef.current && !reducedMotion) {
        ScrollTrigger.create({
          trigger: sectionRef.current,
          start: "top top",
          end: "bottom top",
          scrub: 0.6,
          onUpdate: (self) => {
            progressRef.current = self.progress;
          },
        });
      }
    }, sectionRef);

    return () => ctx.revert();
  }, [reducedMotion]);

  return (
    <section ref={sectionRef} className="relative flex min-h-[100svh] w-full items-center overflow-hidden bg-black pt-[var(--header-height)]">
      <div className="pointer-events-none absolute inset-0 bg-grid-lines bg-[size:52px_52px] opacity-[0.35]" aria-hidden="true" />
      <div className="pointer-events-none absolute -left-40 top-1/3 h-[560px] w-[560px] rounded-full bg-orange-burnt/25 blur-[140px]" aria-hidden="true" />
      <div className="pointer-events-none absolute right-0 top-0 h-full w-1/2 bg-gradient-to-l from-black via-black/40 to-transparent" aria-hidden="true" />

      <div className="relative z-10 mx-auto grid w-full max-w-[1440px] grid-cols-1 items-center gap-10 px-6 md:grid-cols-2 md:px-10">
        <div className="max-w-xl">
          <p className="hero-reveal gk-eyebrow mb-6">Founder-Led Technology System</p>
          <h1 ref={headingRef} className="hero-reveal gk-heading text-[13vw] text-warmwhite sm:text-6xl md:text-[4.2rem]">
            WE BUILD THE
            <br />
            <span className="text-orange-primary">SYSTEMS</span>
            <br />
            BEHIND THE
            <br />
            BUSINESS.
          </h1>
          <p className="hero-reveal mt-6 max-w-md text-sm leading-relaxed text-muted md:text-base">
            GRIDKEEP designs and engineers AI, automation, software, cybersecurity, cloud infrastructure, and
            immersive digital experiences for businesses that need more than disconnected tools.
          </p>
          <div className="hero-reveal mt-9 flex flex-wrap items-center gap-4">
            <LinkButton href="/contact">Enter The System →</LinkButton>
            <LinkButton href="/services" variant="secondary">
              Explore Capabilities
            </LinkButton>
          </div>
        </div>

        <div className="relative h-[420px] w-full sm:h-[520px] md:h-[640px]">
          <SceneCanvas
            eager
            strongBloom
            camera={{ position: [0, 0, 8.2], fov: 36 }}
            posterLabel="GRIDKEEP reactor core"
          >
            <HeroReactorScene progressRef={progressRef} reducedMotion={reducedMotion} />
          </SceneCanvas>
          <span className="pointer-events-none absolute inset-0 flex items-center justify-center font-mono text-[11px] uppercase tracking-[0.4em] text-orange-hot/90">
            <span className="mt-1">GRIDKEEP</span>
          </span>
        </div>
      </div>

      <div className="absolute right-6 top-1/2 z-10 hidden -translate-y-1/2 flex-col items-center gap-3 md:right-10 md:flex" aria-hidden="true">
        <span className="font-mono text-[11px] text-orange-primary">01</span>
        <span className="h-16 w-px bg-line" />
        <span className="font-mono text-[11px] text-muted">10</span>
      </div>

      <div className="absolute bottom-8 left-6 z-10 flex items-center gap-3 md:left-10">
        <span className="h-2 w-2 rounded-full bg-orange-primary animate-pulse-glow" aria-hidden="true" />
        <span className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">Scroll to explore</span>
      </div>
    </section>
  );
}
