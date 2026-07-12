"use client";

import dynamic from "next/dynamic";
import PrototypeStage from "@/components/three/PrototypeStage";
import Reveal from "@/components/ui/Reveal";
import { useScrollProgress } from "@/hooks/useScrollProgress";
import { SITE } from "@/lib/site";

const FounderConsole = dynamic(() => import("@/components/three/prototypes/FounderConsole"), { ssr: false });

const PRINCIPLES = [
  { title: "Systems before features", detail: "Architecture is decided before a single screen is designed." },
  { title: "Security before scale", detail: "Access control and data boundaries are built in, not bolted on." },
  { title: "Business outcomes before technical noise", detail: "Every system is judged by the operational problem it solves." },
];

export default function FounderSection() {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top 70%",
    end: "bottom 30%",
    scrub: 0.8,
  });

  return (
    <section
      ref={sectionRef}
      aria-labelledby="founder-heading"
      className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-24 sm:px-8"
    >
      <div className="mx-auto grid max-w-[1600px] items-center gap-14 lg:grid-cols-2 lg:gap-20">
        <div className="order-2 lg:order-1">
          <Reveal>
            <p className="gk-eyebrow">Founder Systems</p>
            <h2 id="founder-heading" className="font-display mt-4 text-4xl font-bold uppercase leading-tight sm:text-5xl">
              {SITE.founder}
            </h2>
            <p className="font-mono-tech mt-2 text-sm uppercase tracking-[0.14em] text-gk-orange">
              Founder &amp; Systems Architect
            </p>
            <p className="mt-6 max-w-lg text-base leading-relaxed text-gk-grey">
              GRIDKEEP is founder-led by design. Technical execution, commercial understanding,
              and accountability stay connected through one operating standard.
            </p>
            <dl className="mt-9 space-y-5">
              {PRINCIPLES.map((principle) => (
                <div key={principle.title} className="border-l-2 border-gk-orange pl-4">
                  <dt className="font-display text-lg font-semibold text-gk-white">{principle.title}</dt>
                  <dd className="mt-1 text-sm text-gk-grey">{principle.detail}</dd>
                </div>
              ))}
            </dl>
          </Reveal>
        </div>

        <div className="order-1 lg:order-2">
          <div className="relative h-[420px] sm:h-[500px]">
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
        </div>
      </div>
    </section>
  );
}
