import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata } from "@/lib/seo";
import { articles, getReadingTime } from "@/data/insights";
import { PageHeader } from "@/components/ui/PageHeader";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbSchema } from "@/lib/schema";
import { formatDate } from "@/lib/utils";

export const metadata: Metadata = buildMetadata({
  title: "Insights",
  description:
    "Original, practical writing on AI, automation, software, security, and digital strategy — grounded in real implementation work, not trend-chasing.",
  path: "/insights",
});

export default function InsightsPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Insights", path: "/insights" },
          ]),
        ]}
      />
      <PageHeader
        eyebrow="Insights"
        title="Insights"
        description="Original, practical writing on AI, automation, software, security, and digital strategy — grounded in the work of building and shipping these systems for real businesses, not trend-chasing."
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Insights", href: "/insights" },
        ]}
      />

      <section
        className="container-edge border-b border-[var(--color-line)] py-24 md:py-32"
        aria-labelledby="insights-list-heading"
      >
        <h2 id="insights-list-heading" className="sr-only">
          All articles
        </h2>
        <ul className="border-t border-[var(--color-line)]">
          {articles.map((article) => (
            <li key={article.slug} className="border-b border-[var(--color-line)]">
              <Link
                href={`/insights/${article.slug}`}
                className="group grid grid-cols-1 gap-6 py-10 transition-colors hover:bg-[var(--color-surface)] md:grid-cols-[1fr_auto] md:gap-8 md:py-14"
              >
                <div className="max-w-3xl">
                  <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
                    {article.category}
                  </p>
                  <h3 className="mt-3 font-display text-3xl uppercase text-[var(--color-off-white)] transition-colors group-hover:text-[var(--color-blood-red)] md:text-4xl">
                    {article.title}
                  </h3>
                  <p className="mt-4 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                    {article.excerpt}
                  </p>
                  <p className="mt-6 font-mono text-xs uppercase tracking-[0.1em] text-[var(--color-muted)]">
                    {formatDate(article.publishedAt)} · {getReadingTime(article)} min read
                  </p>
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
    </>
  );
}
