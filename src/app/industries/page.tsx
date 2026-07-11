import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { Reveal } from "@/components/ui/Reveal";
import { buildMetadata } from "@/lib/seo";
import { webPageSchema } from "@/lib/schema";
import { industries } from "@/data/industries";
import { getServiceBySlug } from "@/data/services";

export const metadata: Metadata = buildMetadata({
  title: "Industries",
  description:
    "Industries GRIDKEEP works with, including professional services, retail and hospitality, real estate and construction, financial services, healthcare, and logistics.",
  path: "/industries",
});

export default function IndustriesPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "Industries GRIDKEEP Serves",
          description: "Industries GRIDKEEP works with.",
          path: "/industries",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Industries", path: "/industries" }]} />
      <PageHero
        eyebrow="Industries"
        title="Built for how your industry actually operates."
        description="GRIDKEEP's systems are shaped around the operational reality of each industry, not a one-size-fits-all template."
      />

      <section className="mx-auto grid max-w-[1600px] grid-cols-1 gap-px border border-line bg-line px-0 pb-32 md:grid-cols-2 md:px-10">
        {industries.map((industry, index) => (
          <Reveal key={industry.slug} delay={index * 0.03}>
            <div className="flex h-full flex-col justify-between bg-black p-8">
              <div>
                <h2 className="font-display text-2xl text-warm">{industry.name}</h2>
                <p className="mt-3 text-sm text-muted">{industry.description}</p>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                {industry.relevantServices.map((slug) => {
                  const service = getServiceBySlug(slug);
                  if (!service) return null;
                  return (
                    <Link
                      key={slug}
                      href={`/services/${slug}`}
                      className="font-mono text-[10px] uppercase tracking-widest2 text-orange hover:text-orange-bright"
                    >
                      {service.shortName}
                    </Link>
                  );
                })}
              </div>
            </div>
          </Reveal>
        ))}
      </section>
    </>
  );
}
