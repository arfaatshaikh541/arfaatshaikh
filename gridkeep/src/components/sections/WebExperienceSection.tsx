"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import PrototypeStage from "@/components/three/PrototypeStage";
import Reveal from "@/components/ui/Reveal";
import { useScrollProgress } from "@/hooks/useScrollProgress";

const WebExperienceRig = dynamic(() => import("@/components/three/prototypes/WebExperienceRig"), { ssr: false });

const LAYOUTS = ["Desktop", "Tablet", "Mobile"];

export default function WebExperienceSection() {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top 70%",
    end: "bottom 30%",
    scrub: 0.8,
  });
  const [layoutIndex, setLayoutIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      const p = progressRef.current.value;
      const idx = p < 0.4 ? 0 : p < 0.75 ? 1 : 2;
      setLayoutIndex((prev) => (prev !== idx ? idx : prev));
    }, 120);
    return () => clearInterval(id);
  }, [progressRef]);

  return (
    <section
      ref={sectionRef}
      aria-labelledby="web-experience-heading"
      className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-24 sm:px-8"
    >
      <div className="mx-auto grid max-w-[1600px] items-center gap-12 lg:grid-cols-2 lg:gap-16">
        <div>
          <Reveal>
            <p className="gk-eyebrow">Interface Testing Rig</p>
            <h2 id="web-experience-heading" className="font-display mt-4 max-w-xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
              Web experiences, <span className="gk-orange-text">tested like hardware.</span>
            </h2>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-gk-grey">
              A calibrated interface rig with a camera tracking module and articulated mounting
              arm. The display panel is physically retested across desktop, tablet, and mobile
              layouts before an experience ships.
            </p>
            <div className="mt-8 flex gap-2" aria-label="Layout being tested">
              {LAYOUTS.map((layout, i) => (
                <span
                  key={layout}
                  className={`font-mono-tech border px-4 py-2 text-xs uppercase tracking-[0.12em] transition-colors ${
                    i === layoutIndex ? "border-gk-orange text-gk-orange" : "border-gk-steel text-gk-grey-dim"
                  }`}
                >
                  {layout}
                </span>
              ))}
            </div>
          </Reveal>
        </div>

        <div className="relative h-[380px] sm:h-[460px]">
          <PrototypeStage
            title="Web Experience Testing Rig"
            description="A calibration rig with articulated mounting arms, a camera tracking module, and a responsive display panel that physically resizes as it is tested across desktop, tablet, and mobile layouts."
            className="h-full w-full"
            cameraPosition={[1.6, 0.4, 2.4]}
            fov={36}
          >
            <WebExperienceRig progressRef={progressRef} />
          </PrototypeStage>
        </div>
      </div>
    </section>
  );
}
