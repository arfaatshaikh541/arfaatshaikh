import Link from "next/link";
import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import PageIntro from "@/components/sections/PageIntro";
import { insights } from "@/data/insights";

export const metadata = buildMetadata({
  title: "Insights",
  description: "GRIDKEEP insights on systems thinking, business automation, AI agents and founder-led technology engineering.",
  path: "/insights",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "Insights", path: "/insights" },
];

export default function InsightsPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <Breadcrumbs items={crumbs} />
      <PageIntro
        eyebrow="Insights"
        title={
          <>
            NOTES FROM INSIDE <span className="text-orange-primary">THE SYSTEM.</span>
          </>
        }
        description="Perspectives on systems thinking, automation, and applied AI from GRIDKEEP's founder."
      />

      <section className="border-b border-line bg-black-near py-16 md:py-24" aria-label="All articles">
        <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-5 px-6 md:px-10 lg:grid-cols-3">
          {insights.map((article) => (
            <Link key={article.slug} href={`/insights/${article.slug}`} className="gk-card group flex flex-col p-6">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-orange-primary">{article.category}</span>
              <h2 className="mt-3 font-display text-lg uppercase tracking-wide text-warmwhite">{article.title}</h2>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-muted">{article.summary}</p>
              <div className="mt-5 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.1em] text-muted">
                <time dateTime={article.date}>{new Date(article.date).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}</time>
                <span>{article.readTime}</span>
              </div>
              <span className="mt-4 inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-warmwhite/70 transition-colors group-hover:text-orange-bright">
                Read Article <span className="transition-transform group-hover:translate-x-1">→</span>
              </span>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
