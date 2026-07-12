"use client";

import Link from "next/link";
import PrototypeStage from "@/components/three/PrototypeStage";
import HeroReactor from "@/components/three/prototypes/HeroReactor";
import { useScrollProgress } from "@/hooks/useScrollProgress";

export default function HeroSection() {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top top",
    end: "bottom top",
    scrub: 0.8,
  });

  return (
    <section
      ref={sectionRef}
      aria-labelledby="hero-heading"
      className="gk-grid-bg relative flex min-h-[92vh] items-center overflow-hidden border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8"
    >
      <div className="mx-auto grid w-full max-w-[1600px] items-center gap-12 lg:grid-cols-2 lg:gap-6">
        <div>
          <p className="gk-eyebrow">Founder-Led Technology System</p>
          <h1 id="hero-heading" className="font-display mt-5 text-5xl font-bold uppercase leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl">
            We build the
            <br />
            <span className="gk-orange-text">systems</span>
            <br />
            behind the
            <br />
            business.
          </h1>
          <p className="mt-7 max-w-lg text-base leading-relaxed text-gk-grey sm:text-lg">
            GRIDKEEP designs and engineers AI, automation, software, cybersecurity, cloud
            infrastructure, and immersive digital experiences for businesses that need more than
            disconnected tools.
          </p>
          <div className="mt-9 flex flex-wrap gap-4">
            <Link href="/contact" className="gk-btn gk-btn-primary">
              Enter the System
            </Link>
            <Link href="/services" className="gk-btn gk-btn-ghost">
              Explore Capabilities
            </Link>
          </div>
        </div>

        <div className="relative h-[420px] sm:h-[520px] lg:h-[640px]">
          <PrototypeStage
            title="GRIDKEEP Core Reactor"
            description="A heavy black circular reactor housing with layered structural rings, machined steel plates, and armored aperture shutters. As it activates, the outer ring rotates slowly, the inner ring counter-rotates, and ten segmented shutters unlock and retract to reveal an internal orange energy core stabilizing behind them."
            className="h-full w-full"
            cameraPosition={[0, 0.2, 4.4]}
            fov={36}
          >
            <HeroReactor progressRef={progressRef} />
          </PrototypeStage>
        </div>
      </div>
    </section>
  );
}
