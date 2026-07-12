"use client";

import dynamic from "next/dynamic";
import PrototypeStage from "@/components/three/PrototypeStage";
import Reveal from "@/components/ui/Reveal";
import { useScrollProgress } from "@/hooks/useScrollProgress";

const EcosystemCore = dynamic(() => import("@/components/three/prototypes/EcosystemCore"), { ssr: false });

export default function EcosystemSection() {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top 65%",
    end: "bottom 20%",
    scrub: 0.9,
  });

  return (
    <section
      ref={sectionRef}
      aria-labelledby="ecosystem-heading"
      className="border-b border-gk-graphite bg-gk-black px-5 py-24 sm:px-8"
    >
      <div className="mx-auto max-w-[1600px] text-center">
        <Reveal>
          <p className="gk-eyebrow">GRIDKEEP Ecosystem</p>
          <h2 id="ecosystem-heading" className="font-display mx-auto mt-4 max-w-3xl text-4xl font-bold uppercase leading-[0.95] sm:text-6xl">
            Every system.
            <br />
            <span className="gk-orange-text">One ecosystem.</span>
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-gk-grey">
            AI compute, automation, software, security, cloud, business systems, and web
            experience labs dock into a single control core as one integrated infrastructure.
          </p>
        </Reveal>

        <div className="relative mx-auto mt-14 h-[460px] max-w-4xl sm:h-[620px]">
          <PrototypeStage
            title="GRIDKEEP Ecosystem Architecture"
            description="A central GRIDKEEP control core surrounded by seven satellite system modules — AI compute, automation, software, cybersecurity, cloud, business systems, and web experience — connected by structural docking rails that extend and lock as the ecosystem assembles."
            className="h-full w-full"
            cameraPosition={[0, 2.6, 5.8]}
            fov={42}
          >
            <EcosystemCore progressRef={progressRef} />
          </PrototypeStage>
        </div>
      </div>
    </section>
  );
}
