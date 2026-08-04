import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata } from "@/lib/seo";
import { services } from "@/data/services";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbSchema } from "@/lib/schema";

export const metadata: Metadata = buildMetadata({
  title: "Services",
  description:
    "AI agents and automation, custom software and SaaS, cybersecurity, cloud and DevOps, and immersive web experiences — engineered systems for growing businesses.",
  path: "/services",
});

export default function ServicesPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Services", path: "/services" },
          ]),
        ]}
      />
      <PageHeader
        eyebrow="Capabilities"
        title="Services"
        description="AI agents and automation, custom software and SaaS platforms, cybersecurity, cloud and DevOps, and immersive web experiences — five disciplines, engineered together as one system rather than sold as separate line items."
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Services", href: "/services" },
        ]}
      />

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="services-list-heading">
        <h2 id="services-list-heading" className="sr-only">
          Full list of services
        </h2>
        <ul className="border-t border-[var(--color-line)]">
          {services.map((service, index) => (
            <li key={service.slug} className="border-b border-[var(--color-line)]">
              <Link
                href={`/services/${service.slug}`}
                className="group grid grid-cols-1 gap-6 py-10 transition-colors hover:bg-[var(--color-surface)] md:grid-cols-[80px_1fr_auto] md:gap-8 md:py-14"
              >
                <span className="font-mono text-sm text-[var(--color-muted)]">
                  {String(index + 1).padStart(2, "0")}
                </span>

                <div className="max-w-3xl">
                  <h3 className="font-display text-3xl uppercase text-[var(--color-off-white)] transition-colors group-hover:text-[var(--color-blood-red)] md:text-4xl">
                    {service.name}
                  </h3>
                  <p className="mt-3 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                    {service.tagline}
                  </p>
                  <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[var(--color-muted)]">
                    {service.heroDescription}
                  </p>

                  <ul className="mt-6 flex flex-wrap gap-2">
                    {service.pillars.slice(0, 3).map((pillar) => (
                      <li
                        key={pillar.slug}
                        className="border border-[var(--color-line)] px-4 py-2 font-mono text-[0.65rem] uppercase tracking-[0.08em] text-[var(--color-off-white)]"
                      >
                        {pillar.name}
                      </li>
                    ))}
                  </ul>
                </div>

                <span
                  aria-hidden="true"
                  className="hidden font-mono text-lg text-[var(--color-muted)] transition-transform group-hover:translate-x-1 group-hover:text-[var(--color-blood-red)] md:block"
                >
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="py-24 md:py-40" aria-labelledby="services-cta-heading">
        <div className="container-edge">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Start a Project
          </p>
          <h2
            id="services-cta-heading"
            className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl"
          >
            Not sure which service fits your problem?
          </h2>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
            Most projects touch more than one discipline. Tell me what you&apos;re
            trying to solve and I&apos;ll tell you honestly what it actually needs.
          </p>
          <div className="mt-10">
            <CtaLink href="/contact">Start the conversation</CtaLink>
          </div>
        </div>
      </section>
    </>
  );
}
