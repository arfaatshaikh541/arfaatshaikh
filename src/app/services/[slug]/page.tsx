import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { buildMetadata } from "@/lib/seo";
import { services, getServiceBySlug } from "@/data/services";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { serviceSchema, faqSchema, breadcrumbSchema } from "@/lib/schema";

export function generateStaticParams() {
  return services.map((service) => ({ slug: service.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const service = getServiceBySlug(slug);
  if (!service) return {};

  return buildMetadata({
    title: service.name,
    description: service.heroDescription,
    path: `/services/${service.slug}`,
  });
}

export default async function ServicePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const service = getServiceBySlug(slug);
  if (!service) notFound();

  const relatedServices = service.relatedSlugs
    .map((relatedSlug) => getServiceBySlug(relatedSlug))
    .filter((related): related is NonNullable<typeof related> => Boolean(related));

  return (
    <>
      <JsonLd
        data={[
          serviceSchema(service),
          faqSchema(service.faqs),
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Services", path: "/services" },
            { name: service.name, path: `/services/${service.slug}` },
          ]),
        ]}
      />

      <PageHeader
        eyebrow={service.tagline}
        title={service.name}
        description={service.heroDescription}
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Services", href: "/services" },
          { name: service.name, href: `/services/${service.slug}` },
        ]}
      />

      {/* Overview */}
      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="overview-heading">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Overview
        </p>
        <h2 id="overview-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          {service.shortName}, done properly.
        </h2>
        <div className="mt-10 max-w-3xl space-y-6">
          {service.overview.map((paragraph, index) => (
            <p key={index} className="text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
              {paragraph}
            </p>
          ))}
        </div>
      </section>

      {/* Problems Solved */}
      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="problems-heading">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          The Problem
        </p>
        <h2 id="problems-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          What This Solves
        </h2>

        <ul className="mt-12 border-t border-[var(--color-line)]">
          {service.problems.map((problem, index) => (
            <li key={index} className="grid grid-cols-[48px_1fr] gap-4 border-b border-[var(--color-line)] py-6 md:grid-cols-[64px_1fr]">
              <span className="font-mono text-sm text-[var(--color-blood-red)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <p className="max-w-2xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                {problem}
              </p>
            </li>
          ))}
        </ul>
      </section>

      {/* Capabilities */}
      <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="capabilities-heading">
        <div className="container-edge">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            What&apos;s Included
          </p>
          <h2 id="capabilities-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
            Capabilities
          </h2>
        </div>

        <div className="container-edge mt-16 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-2">
          {service.capabilities.map((capability, index) => (
            <div key={capability.title} className="bg-black p-8">
              <span className="font-mono text-xs text-[var(--color-blood-red)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3 className="mt-3 font-display text-xl uppercase text-[var(--color-off-white)]">
                {capability.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">
                {capability.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Pillars */}
      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="pillars-heading">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Sub-Offerings
        </p>
        <h2 id="pillars-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          Inside {service.shortName}
        </h2>

        <div className="mt-12 grid gap-8 md:grid-cols-2 md:gap-x-12 md:gap-y-10">
          {service.pillars.map((pillar) => (
            <div key={pillar.slug} className="border-t border-[var(--color-line)] pt-6">
              <h3 className="font-display text-2xl uppercase text-[var(--color-off-white)]">
                {pillar.name}
              </h3>
              <p className="mt-2 text-sm uppercase tracking-[0.05em] text-[var(--color-blood-red)]">
                {pillar.tagline}
              </p>
              <p className="mt-4 max-w-lg text-base leading-relaxed text-[var(--color-muted)]">
                {pillar.summary}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Process */}
      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="process-heading">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          How It Works
        </p>
        <h2 id="process-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          Process
        </h2>

        <ol className="mt-12 border-t border-[var(--color-line)]">
          {service.process.map((step) => (
            <li key={step.step} className="grid grid-cols-1 gap-3 border-b border-[var(--color-line)] py-8 md:grid-cols-[100px_1fr] md:gap-8">
              <span className="font-mono text-2xl text-[var(--color-blood-red)]">
                {step.step}
              </span>
              <div>
                <h3 className="font-display text-2xl uppercase text-[var(--color-off-white)]">
                  {step.title}
                </h3>
                <p className="mt-3 max-w-2xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                  {step.description}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* Technologies */}
      <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="technologies-heading">
        <div className="container-edge">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Under The Hood
          </p>
          <h2 id="technologies-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
            Technologies
          </h2>
        </div>

        <ul className="container-edge mt-12 flex flex-wrap gap-3">
          {service.technologies.map((technology) => (
            <li
              key={technology}
              className="border border-[var(--color-line)] px-5 py-3 font-mono text-xs uppercase tracking-[0.08em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
            >
              {technology}
            </li>
          ))}
        </ul>
      </section>

      {/* Use Cases */}
      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="use-cases-heading">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Who This Is For
        </p>
        <h2 id="use-cases-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          Use Cases
        </h2>

        <ul className="mt-12 border-t border-[var(--color-line)]">
          {service.useCases.map((useCase, index) => (
            <li key={index} className="grid grid-cols-[48px_1fr] gap-4 border-b border-[var(--color-line)] py-6 md:grid-cols-[64px_1fr]">
              <span className="font-mono text-sm text-[var(--color-blood-red)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <p className="max-w-2xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                {useCase}
              </p>
            </li>
          ))}
        </ul>
      </section>

      {/* FAQs */}
      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="faqs-heading">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Questions
        </p>
        <h2 id="faqs-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          Frequently Asked
        </h2>

        <div className="mt-12 max-w-3xl border-t border-[var(--color-line)]">
          {service.faqs.map((faq, index) => (
            <details key={index} className="group border-b border-[var(--color-line)] py-6">
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6 font-display text-lg uppercase text-[var(--color-off-white)] marker:content-none [&::-webkit-details-marker]:hidden">
                <span>{faq.question}</span>
                <span
                  aria-hidden="true"
                  className="mt-1 shrink-0 font-mono text-lg text-[var(--color-blood-red)] transition-transform group-open:rotate-45"
                >
                  +
                </span>
              </summary>
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                {faq.answer}
              </p>
            </details>
          ))}
        </div>
      </section>

      {/* Related Services */}
      {relatedServices.length > 0 && (
        <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="related-heading">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Related
          </p>
          <h2 id="related-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
            Related Services
          </h2>

          <ul className="mt-12 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-2">
            {relatedServices.map((related) => (
              <li key={related.slug} className="bg-black">
                <Link
                  href={`/services/${related.slug}`}
                  className="group block h-full p-8 transition-colors hover:bg-[var(--color-surface)]"
                >
                  <h3 className="font-display text-2xl uppercase text-[var(--color-off-white)] transition-colors group-hover:text-[var(--color-blood-red)]">
                    {related.name}
                  </h3>
                  <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">
                    {related.tagline}
                  </p>
                  <span
                    aria-hidden="true"
                    className="mt-6 inline-block font-mono text-sm text-[var(--color-muted)] transition-transform group-hover:translate-x-1 group-hover:text-[var(--color-blood-red)]"
                  >
                    →
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Closing CTA */}
      <section className="py-24 md:py-40" aria-labelledby="service-cta-heading">
        <div className="container-edge">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Start a Project
          </p>
          <h2
            id="service-cta-heading"
            className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl"
          >
            Ready to talk about {service.shortName.toLowerCase()}?
          </h2>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
            Tell me about the problem, not just the tool you think you need.
            I&apos;ll reply with an honest read on scope and whether it&apos;s a fit.
          </p>
          <div className="mt-10">
            <CtaLink href="/contact">Start a project</CtaLink>
          </div>
        </div>
      </section>
    </>
  );
}
