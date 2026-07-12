import type { Metadata } from "next";
import Link from "next/link";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import { INSIGHTS } from "@/lib/insights-data";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Insights",
  description: "Notes on systems architecture, security, and applied AI from GRIDKEEP.",
  alternates: { canonical: "/insights" },
  openGraph: { url: "/insights", title: `Insights — ${SITE.name}` },
};

export default function InsightsPage() {
  return (
    <>
      <JsonLd data={webPageSchema({ name: "Insights", description: metadata.description as string, path: "/insights" })} />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Insights", path: "/insights" }]} />

      <section className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">Insights</p>
          <h1 className="font-display mt-4 max-w-2xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            Notes on <span className="gk-orange-text">systems engineering.</span>
          </h1>
        </div>
      </section>

      <section className="bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {INSIGHTS.map((insight) => (
              <Link
                key={insight.slug}
                href={`/insights/${insight.slug}`}
                className="gk-panel flex flex-col gap-3 border border-gk-steel p-6 transition-colors hover:border-gk-orange/60"
              >
                <span className="font-mono-tech text-[0.68rem] uppercase tracking-[0.14em] text-gk-orange">
                  {new Date(insight.datePublished).toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric" })} · {insight.readingTime}
                </span>
                <h2 className="font-display text-xl font-semibold text-gk-white">{insight.title}</h2>
                <p className="text-sm leading-relaxed text-gk-grey">{insight.excerpt}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
