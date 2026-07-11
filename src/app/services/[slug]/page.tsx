import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { ChapterScene } from "@/components/three/ChapterScene";
import { Reveal } from "@/components/ui/Reveal";
import { ButtonLink } from "@/components/ui/Button";
import { buildMetadata } from "@/lib/seo";
import { faqSchema, serviceSchema } from "@/lib/schema";
import { getServiceBySlug, services } from "@/data/services";
import { industries } from "@/data/industries";

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
    description: service.summary,
    path: `/services/${service.slug}`,
  });
}

export default async function ServiceDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const service = getServiceBySlug(slug);
  if (!service) notFound();

  const relatedIndustries = industries.filter((industry) =>
    service.relatedIndustries.includes(industry.slug)
  );

  return (
    <>
      <JsonLd
        data={[
          serviceSchema({ name: service.name, description: service.description, path: `/services/${service.slug}` }),
          ...(service.faqs ? [faqSchema(service.faqs)] : []),
        ]}
      />
      <Breadcrumbs
        items={[
          { name: "Home", path: "/" },
          { name: "Services", path: "/services" },
          { name: service.shortName, path: `/services/${service.slug}` },
        ]}
      />

      <div className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 opacity-70">
          <ChapterScene scene={service.scene} interactive className="h-full w-full" />
        </div>
        <PageHero eyebrow={service.eyebrow} title={service.name} description={service.summary} />
      </div>

      <section className="mx-auto grid max-w-[1600px] grid-cols-1 gap-16 px-6 pb-32 md:grid-cols-3 md:px-10">
        <div className="md:col-span-2">
          <Reveal>
            <h2 className="font-display text-2xl text-warm">Overview</h2>
            <p className="mt-4 text-muted">{service.description}</p>
          </Reveal>

          <Reveal delay={0.06}>
            <h2 className="mt-14 font-display text-2xl text-warm">What's included</h2>
            <ul className="mt-4 flex flex-col gap-3">
              {service.capabilities.map((capability) => (
                <li key={capability} className="flex items-start gap-3 border-b border-line pb-3 text-warm">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 bg-orange" aria-hidden="true" />
                  {capability}
                </li>
              ))}
            </ul>
          </Reveal>

          {service.faqs && (
            <Reveal delay={0.12}>
              <h2 className="mt-14 font-display text-2xl text-warm">Frequently asked questions</h2>
              <div className="mt-4 flex flex-col gap-6">
                {service.faqs.map((faq) => (
                  <div key={faq.question}>
                    <h3 className="font-display text-lg text-warm">{faq.question}</h3>
                    <p className="mt-2 text-muted">{faq.answer}</p>
                  </div>
                ))}
              </div>
            </Reveal>
          )}
        </div>

        <aside>
          <Reveal delay={0.08}>
            <div className="border border-line p-6">
              <span className="font-mono text-xs uppercase tracking-widest2 text-orange">
                Relevant industries
              </span>
              <ul className="mt-4 flex flex-col gap-3">
                {relatedIndustries.map((industry) => (
                  <li key={industry.slug}>
                    <Link href="/industries" className="text-sm text-warm hover:text-orange">
                      {industry.name}
                    </Link>
                  </li>
                ))}
              </ul>
              <div className="mt-8">
                <ButtonLink href="/contact" className="w-full text-center">
                  Discuss this service
                </ButtonLink>
              </div>
            </div>
          </Reveal>
        </aside>
      </section>
    </>
  );
}
