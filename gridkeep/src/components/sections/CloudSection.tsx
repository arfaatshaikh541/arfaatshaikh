"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import PrototypeStage from "@/components/three/PrototypeStage";
import Reveal from "@/components/ui/Reveal";
import { useScrollProgress } from "@/hooks/useScrollProgress";

const CloudArray = dynamic(() => import("@/components/three/prototypes/CloudArray"), { ssr: false });

const STEPS = ["Build", "Test", "Containerize", "Deploy", "Monitor", "Recover"];

export default function CloudSection() {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top 70%",
    end: "bottom 30%",
    scrub: 0.8,
  });
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      const idx = Math.min(STEPS.length - 1, Math.floor(progressRef.current.value * STEPS.length));
      setStepIndex((prev) => (prev !== idx ? idx : prev));
    }, 120);
    return () => clearInterval(id);
  }, [progressRef]);

  return (
    <section
      ref={sectionRef}
      aria-labelledby="cloud-heading"
      className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-24 sm:px-8"
    >
      <div className="mx-auto max-w-[1600px]">
        <Reveal>
          <p className="gk-eyebrow">Deployment Lab</p>
          <h2 id="cloud-heading" className="font-display mt-4 max-w-2xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            Cloud &amp; DevOps <span className="gk-orange-text">infrastructure</span>
          </h2>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-gk-grey">
            A physical deployment lab: a code package moves through build, test, containerization,
            deployment, monitoring, and recovery — every stage observable, every failure isolated
            before it reaches production.
          </p>
        </Reveal>

        <ol className="mt-10 flex flex-wrap gap-2" aria-label="Deployment pipeline stages">
          {STEPS.map((step, i) => (
            <li
              key={step}
              className={`font-mono-tech flex items-center gap-2 border px-4 py-2 text-xs uppercase tracking-[0.12em] transition-colors ${
                i === stepIndex ? "border-gk-orange text-gk-orange" : "border-gk-steel text-gk-grey-dim"
              }`}
            >
              <span>{String(i + 1).padStart(2, "0")}</span>
              {step}
            </li>
          ))}
        </ol>

        <div className="relative mt-10 h-[420px] sm:h-[520px]">
          <PrototypeStage
            title="Cloud Deployment Array"
            description="A modular edge-cloud infrastructure rack with hot-swappable compute nodes, a network switch, and an observability console. A build package deploys across nodes, traffic balances dynamically, and a failed node is isolated automatically while the array stays online."
            className="h-full w-full"
            cameraPosition={[1.9, 0.8, 2.5]}
            fov={36}
          >
            <CloudArray progressRef={progressRef} />
          </PrototypeStage>
        </div>
      </div>
    </section>
  );
}
