"use client";

import { type ComponentType } from "react";
import PrototypeStage from "@/components/three/PrototypeStage";
import Reveal from "@/components/ui/Reveal";
import { useScrollProgress } from "@/hooks/useScrollProgress";
import type { ProgressRef } from "@/hooks/useScrollProgress";

type PrototypeProps = { progressRef?: ProgressRef };

type Props = {
  number: string;
  title: string;
  description: string;
  copy: string;
  labels: string[];
  Prototype: ComponentType<PrototypeProps>;
  reverse?: boolean;
  cameraPosition?: [number, number, number];
};

export default function Chapter({
  number,
  title,
  description,
  copy,
  labels,
  Prototype,
  reverse = false,
  cameraPosition = [2.6, 1.4, 3.2],
}: Props) {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top 75%",
    end: "bottom 25%",
    scrub: 0.8,
  });

  return (
    <section
      ref={sectionRef}
      aria-labelledby={`chapter-${number}-heading`}
      className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-24 sm:px-8"
    >
      <div
        className={`mx-auto grid max-w-[1600px] items-center gap-12 lg:grid-cols-2 lg:gap-16 ${
          reverse ? "lg:[direction:rtl]" : ""
        }`}
      >
        <div className={reverse ? "lg:[direction:ltr]" : ""}>
          <Reveal>
            <span className="font-display block text-6xl font-bold text-gk-steel-light sm:text-8xl">{number}</span>
            <h2 id={`chapter-${number}-heading`} className="font-display -mt-3 text-3xl font-bold uppercase sm:text-4xl">
              {title}
            </h2>
            <p className="mt-5 max-w-md text-base leading-relaxed text-gk-grey">{copy}</p>
            <ul className="mt-6 flex flex-wrap gap-2">
              {labels.map((label) => (
                <li
                  key={label}
                  className="font-mono-tech rounded-none border border-gk-steel px-3 py-1.5 text-[0.68rem] uppercase tracking-[0.1em] text-gk-grey"
                >
                  {label}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>

        <div className={reverse ? "lg:[direction:ltr]" : ""}>
          <div className="relative h-[380px] sm:h-[460px]">
            <PrototypeStage
              title={title}
              description={description}
              className="h-full w-full"
              cameraPosition={cameraPosition}
              fov={36}
            >
              <Prototype progressRef={progressRef} />
            </PrototypeStage>
          </div>
        </div>
      </div>
    </section>
  );
}
