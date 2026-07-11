"use client";

import { useRef } from "react";
import { ChapterScene } from "@/components/three/ChapterScene";
import { ButtonLink } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { CONTACT_EMAIL } from "@/lib/constants";

export function ContactPortalSection() {
  const sectionRef = useRef<HTMLElement | null>(null);

  return (
    <section
      ref={sectionRef}
      className="relative flex min-h-[130vh] flex-col border-t border-line bg-black"
      aria-labelledby="contact-portal-heading"
    >
      <div className="sticky top-0 flex h-screen w-full flex-col items-center justify-center overflow-hidden">
        <ChapterScene scene="portal" sectionRef={sectionRef} className="absolute inset-0" />

        <div className="relative z-10 mx-auto flex max-w-2xl flex-col items-center px-6 text-center">
          <Reveal>
            <SectionLabel index="14" label="Start a project" />
          </Reveal>
          <Reveal delay={0.08}>
            <h2 id="contact-portal-heading" className="mt-6 text-balance font-display text-4xl text-warm md:text-6xl">
              Ready to build the system?
            </h2>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-6 text-balance text-muted">
              Tell us what you're running into, and where you want the business to be.
              We'll respond directly — no account managers, no handoffs.
            </p>
          </Reveal>
          <Reveal delay={0.24}>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <ButtonLink href="/contact" variant="primary">
                Open contact form
              </ButtonLink>
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="font-mono text-xs uppercase tracking-widest2 text-muted hover:text-orange"
              >
                {CONTACT_EMAIL}
              </a>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
