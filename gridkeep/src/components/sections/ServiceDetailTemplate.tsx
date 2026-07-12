"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import type { ComponentType } from "react";
import PrototypeStage from "@/components/three/PrototypeStage";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import FaqAccordion from "@/components/ui/FaqAccordion";
import Reveal from "@/components/ui/Reveal";
import JsonLd from "@/components/ui/JsonLd";
import { useScrollProgress } from "@/hooks/useScrollProgress";
import { SERVICES, type ServiceDefinition, type ServiceSlug } from "@/lib/services-data";
import { faqSchema, serviceSchema } from "@/lib/schema";

const AIInferenceNode = dynamic(() => import("@/components/three/prototypes/AIInferenceNode"), { ssr: false });
const AutomationCell = dynamic(() => import("@/components/three/prototypes/AutomationCell"), { ssr: false });
const SoftwareRack = dynamic(() => import("@/components/three/prototypes/SoftwareRack"), { ssr: false });
const CyberVault = dynamic(() => import("@/components/three/prototypes/CyberVault"), { ssr: false });
const CloudArray = dynamic(() => import("@/components/three/prototypes/CloudArray"), { ssr: false });
const BusinessHub = dynamic(() => import("@/components/three/prototypes/BusinessHub"), { ssr: false });
const WebExperienceRig = dynamic(() => import("@/components/three/prototypes/WebExperienceRig"), { ssr: false });

type PrototypeProps = { progressRef?: ReturnType<typeof useScrollProgress>["progressRef"] };

const PROTOTYPES: Record<ServiceSlug, { Component: ComponentType<PrototypeProps>; cameraPosition: [number, number, number] }> = {
  "ai-agents": { Component: AIInferenceNode, cameraPosition: [2.1, 1, 2.6] },
  automation: { Component: AutomationCell, cameraPosition: [2.8, 1.2, 3.2] },
  "software-saas": { Component: SoftwareRack, cameraPosition: [1.6, 0.6, 2.3] },
  cybersecurity: { Component: CyberVault, cameraPosition: [1.6, 0.8, 2.3] },
  "cloud-devops": { Component: CloudArray, cameraPosition: [1.9, 0.8, 2.5] },
  "business-systems": { Component: BusinessHub, cameraPosition: [1.9, 1.3, 2.1] },
  "web-experiences": { Component: WebExperienceRig, cameraPosition: [1.7, 0.4, 2.5] },
};

export default function ServiceDetailTemplate({ service }: { service: ServiceDefinition }) {
  const { sectionRef, progressRef } = useScrollProgress<HTMLDivElement>({
    start: "top top",
    end: "bottom top",
    scrub: 0.8,
  });
  const prototype = PROTOTYPES[service.slug];
  const related = SERVICES.filter((s) => s.slug !== service.slug).slice(0, 3);

  return (
    <>
      <JsonLd
        data={serviceSchema({
          name: service.name,
          description: service.description,
          path: `/services/${service.slug}`,
          serviceType: service.shortName,
        })}
      />
      <JsonLd data={faqSchema(service.faqs)} />

      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Services", path: "/services" }, { name: service.name, path: `/services/${service.slug}` }]} />

      <section
        ref={sectionRef}
        aria-labelledby="service-hero-heading"
        className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-16 sm:px-8"
      >
        <div className="mx-auto grid max-w-[1600px] items-center gap-12 lg:grid-cols-2 lg:gap-16">
          <div>
            <span className="gk-eyebrow">System {service.index}</span>
            <h1 id="service-hero-heading" className="font-display mt-4 text-4xl font-bold uppercase leading-tight sm:text-5xl">
              {service.name}
            </h1>
            <p className="mt-4 text-lg font-medium text-gk-orange">{service.tagline}</p>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-gk-grey">{service.heroDescription}</p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link href="/contact" className="gk-btn gk-btn-primary">
                Start a Project
              </Link>
              <Link href="/services" className="gk-btn gk-btn-ghost">
                All Services
              </Link>
            </div>
          </div>
          <div className="relative h-[360px] sm:h-[460px]">
            <PrototypeStage
              title={service.prototypeName}
              description={service.heroDescription}
              className="h-full w-full"
              cameraPosition={prototype.cameraPosition}
              fov={36}
            >
              <prototype.Component progressRef={progressRef} />
            </PrototypeStage>
          </div>
        </div>
      </section>

      <section aria-labelledby="problems-heading" className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <Reveal>
            <p className="gk-eyebrow">Problems Solved</p>
            <h2 id="problems-heading" className="font-display mt-3 max-w-xl text-3xl font-bold uppercase sm:text-4xl">
              What this system replaces
            </h2>
          </Reveal>
          <ul className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-3">
            {service.problems.map((problem) => (
              <li key={problem} className="gk-panel border border-gk-steel p-6 text-sm leading-relaxed text-gk-grey">
                {problem}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="architecture-heading" className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <Reveal>
            <p className="gk-eyebrow">System Architecture</p>
            <h2 id="architecture-heading" className="font-display mt-3 max-w-xl text-3xl font-bold uppercase sm:text-4xl">
              How it&apos;s built
            </h2>
          </Reveal>
          <dl className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {service.architecture.map((layer, i) => (
              <div key={layer.label} className="border-l-2 border-gk-orange pl-4">
                <dt className="font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-orange">
                  {String(i + 1).padStart(2, "0")} {layer.label}
                </dt>
                <dd className="mt-2 text-sm leading-relaxed text-gk-grey">{layer.detail}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section aria-labelledby="process-heading" className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <Reveal>
            <p className="gk-eyebrow">Process</p>
            <h2 id="process-heading" className="font-display mt-3 max-w-xl text-3xl font-bold uppercase sm:text-4xl">
              How we work
            </h2>
          </Reveal>
          <ol className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {service.process.map((step, i) => (
              <li key={step.step} className="gk-panel border border-gk-steel p-6">
                <span className="font-display text-3xl font-bold text-gk-steel-light">{String(i + 1).padStart(2, "0")}</span>
                <h3 className="font-display mt-2 text-lg font-semibold text-gk-white">{step.step}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gk-grey">{step.detail}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="capabilities-heading" className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto grid max-w-[1600px] gap-14 lg:grid-cols-2">
          <div>
            <Reveal>
              <p className="gk-eyebrow">Capabilities</p>
              <h2 id="capabilities-heading" className="font-display mt-3 text-3xl font-bold uppercase sm:text-4xl">
                What we deliver
              </h2>
              <ul className="mt-8 space-y-3">
                {service.capabilities.map((cap) => (
                  <li key={cap} className="flex items-start gap-3 text-sm text-gk-grey">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 bg-gk-orange" aria-hidden="true" />
                    {cap}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
          <div>
            <Reveal delay={0.1}>
              <p className="gk-eyebrow">Use Cases</p>
              <h2 className="font-display mt-3 text-3xl font-bold uppercase sm:text-4xl">Where it applies</h2>
              <ul className="mt-8 space-y-3">
                {service.useCases.map((useCase) => (
                  <li key={useCase} className="flex items-start gap-3 text-sm text-gk-grey">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 bg-gk-orange" aria-hidden="true" />
                    {useCase}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </div>
      </section>

      <section aria-labelledby="faq-heading" className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <p className="gk-eyebrow">FAQ</p>
            <h2 id="faq-heading" className="font-display mt-3 text-3xl font-bold uppercase sm:text-4xl">
              Common questions
            </h2>
          </Reveal>
          <div className="mt-10">
            <FaqAccordion items={service.faqs} />
          </div>
        </div>
      </section>

      <section aria-labelledby="related-heading" className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">Related Systems</p>
          <h2 id="related-heading" className="font-display mt-3 text-3xl font-bold uppercase sm:text-4xl">
            Explore more
          </h2>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {related.map((r) => (
              <Link
                key={r.slug}
                href={`/services/${r.slug}`}
                className="gk-panel border border-gk-steel p-6 transition-colors hover:border-gk-orange/60"
              >
                <span className="gk-eyebrow">{r.index}</span>
                <h3 className="font-display mt-2 text-lg font-semibold text-gk-white">{r.name}</h3>
                <p className="mt-2 text-sm text-gk-grey">{r.tagline}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="cta-heading" className="bg-gk-black px-5 py-24 text-center sm:px-8">
        <h2 id="cta-heading" className="font-display mx-auto max-w-2xl text-3xl font-bold uppercase sm:text-4xl">
          Ready to engineer <span className="gk-orange-text">{service.shortName.toLowerCase()}</span> that works?
        </h2>
        <div className="mt-8">
          <Link href="/contact" className="gk-btn gk-btn-primary">
            Open a Project Channel
          </Link>
        </div>
      </section>
    </>
  );
}
