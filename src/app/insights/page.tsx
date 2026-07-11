import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { Reveal } from "@/components/ui/Reveal";
import { buildMetadata } from "@/lib/seo";
import { webPageSchema } from "@/lib/schema";
import { getAllInsightsMeta } from "@/lib/insights";
import { formatDate } from "@/lib/utils";

export const metadata: Metadata = buildMetadata({
  title: "Insights",
  description:
    "GRIDKEEP insights on AI agents, business automation, custom software, cybersecurity, cloud infrastructure, and connected business systems.",
  path: "/insights",
});

export default function InsightsPage() {
  const insights = getAllInsightsMeta();
  const categories = Array.from(new Set(insights.map((item) => item.category)));

  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "GRIDKEEP Insights",
          description: "Articles on AI, automation, software, security, and infrastructure.",
          path: "/insights",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Insights", path: "/insights" }]} />
      <PageHero
        eyebrow="Insights"
        title="Written by the people doing the work."
        description="Practical perspective on AI, automation, software, security, and infrastructure — no keyword-stuffed filler."
      />

      <section className="mx-auto max-w-[1600px] px-6 pb-32 md:px-10">
        <div className="mb-10 flex flex-wrap gap-3">
          {categories.map((category) => (
            <span
              key={category}
              className="border border-line px-3 py-1 font-mono text-[10px] uppercase tracking-widest2 text-muted"
            >
              {category}
            </span>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-px border border-line bg-line md:grid-cols-2">
          {insights.map((insight, index) => (
            <Reveal key={insight.slug} delay={index * 0.02}>
              <Link
                href={`/insights/${insight.slug}`}
                className="group flex h-full flex-col justify-between bg-black p-8 transition-colors hover:bg-surface"
              >
                <div>
                  <span className="font-mono text-[10px] uppercase tracking-widest2 text-orange">
                    {insight.category}
                  </span>
                  <h2 className="mt-4 font-display text-2xl text-warm group-hover:text-orange-bright">
                    {insight.title}
                  </h2>
                  <p className="mt-3 text-sm text-muted">{insight.description}</p>
                </div>
                <div className="mt-8 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest2 text-muted">
                  <span>{formatDate(insight.publishedAt)}</span>
                  <span>{insight.readingTime}</span>
                </div>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>
    </>
  );
}
