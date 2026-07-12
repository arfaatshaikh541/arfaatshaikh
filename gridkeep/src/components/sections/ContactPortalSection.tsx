"use client";

import dynamic from "next/dynamic";
import PrototypeStage from "@/components/three/PrototypeStage";
import Reveal from "@/components/ui/Reveal";
import ContactForm from "@/components/ui/ContactForm";
import { useScrollProgress } from "@/hooks/useScrollProgress";
import { SITE } from "@/lib/site";

const ContactPortalRig = dynamic(() => import("@/components/three/prototypes/ContactPortalRig"), { ssr: false });

export default function ContactPortalSection() {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top 70%",
    end: "bottom 30%",
    scrub: 0.8,
  });

  return (
    <section
      ref={sectionRef}
      id="contact"
      aria-labelledby="contact-heading"
      className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-24 sm:px-8"
    >
      <div className="mx-auto max-w-[1600px]">
        <Reveal>
          <p className="gk-eyebrow">Project Intake Chamber</p>
          <h2 id="contact-heading" className="font-display mt-4 max-w-2xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            Open a <span className="gk-orange-text">project channel.</span>
          </h2>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-gk-grey">
            Tell us what needs to be built. A founder-led team reviews every intake directly —
            no account managers between you and the engineers.
          </p>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
          <div className="relative h-[320px] sm:h-[420px] lg:h-auto">
            <PrototypeStage
              title="Project Intake Portal"
              description="A circular mechanical door set into a heavy industrial housing on a floor platform, with locking mechanisms and an orange illuminated perimeter. The iris door opens as a project intake begins, revealing a contained inner glow."
              className="h-full w-full"
              cameraPosition={[0, 0.3, 4.6]}
              fov={38}
            >
              <ContactPortalRig progressRef={progressRef} />
            </PrototypeStage>
          </div>

          <div>
            <ContactForm />
            <p className="font-mono-tech mt-6 text-xs uppercase tracking-[0.1em] text-gk-grey-dim">
              Direct: <a href={`mailto:${SITE.email}`} className="text-gk-orange">{SITE.email}</a> · {SITE.location}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
