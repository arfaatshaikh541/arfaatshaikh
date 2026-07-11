import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { Reveal } from "@/components/ui/Reveal";
import { buildMetadata } from "@/lib/seo";
import { webPageSchema } from "@/lib/schema";
import { services } from "@/data/services";

export const metadata: Metadata = buildMetadata({
  title: "Services",
  description:
    "GRIDKEEP services: AI and AI agents, business automation, custom software and SaaS, cybersecurity, cloud and DevOps, business systems, and immersive web experiences.",
  path: "/services",
});

export default function ServicesPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "GRIDKEEP Services",
          description: "The full range of GRIDKEEP technology services.",
          path: "/services",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Services", path: "/services" }]} />
      <PageHero
        eyebrow="Capabilities"
        title="Systems, not one-off deliverables."
        description="Every GRIDKEEP service is engineered to work as part of one connected technology architecture — not a standalone project handed off and forgotten."
      />

      <section className="mx-auto max-w-[1600px] px-6 pb-32 md:px-10">
        <div className="grid grid-cols-1 gap-px border border-line bg-line md:grid-cols-2">
          {services.map((service, index) => (
            <Reveal key={service.slug} delay={index * 0.03}>
              <Link
                href={`/services/${service.slug}`}
                className="group flex h-full flex-col justify-between bg-black p-8 transition-colors hover:bg-surface"
              >
                <div>
                  <span className="font-mono text-[10px] uppercase tracking-widest2 text-orange">
                    {String(index + 1).padStart(2, "0")} — {service.eyebrow}
                  </span>
                  <h2 className="mt-4 font-display text-2xl text-warm group-hover:text-orange-bright">
                    {service.name}
                  </h2>
                  <p className="mt-3 text-sm text-muted">{service.summary}</p>
                </div>
                <span className="mt-8 font-mono text-xs uppercase tracking-widest2 text-orange">
                  View service →
                </span>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>
    </>
  );
}
