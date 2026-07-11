import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { Reveal } from "@/components/ui/Reveal";
import { buildMetadata } from "@/lib/seo";
import { articleSchema } from "@/lib/schema";
import { getAllInsightsMeta, getInsightBySlug, getRelatedInsights } from "@/lib/insights";
import { formatDate } from "@/lib/utils";

export function generateStaticParams() {
  return getAllInsightsMeta().map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const insight = await getInsightBySlug(slug);
  if (!insight) return {};
  return buildMetadata({
    title: insight.title,
    description: insight.description,
    path: `/insights/${insight.slug}`,
    type: "article",
  });
}

export default async function InsightDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const insight = await getInsightBySlug(slug);
  if (!insight) notFound();

  const related = getRelatedInsights(insight.slug, insight.category);

  return (
    <>
      <JsonLd
        data={articleSchema({
          title: insight.title,
          description: insight.description,
          slug: insight.slug,
          publishedAt: insight.publishedAt,
          modifiedAt: insight.modifiedAt,
          author: insight.author,
        })}
      />
      <Breadcrumbs
        items={[
          { name: "Home", path: "/" },
          { name: "Insights", path: "/insights" },
          { name: insight.title, path: `/insights/${insight.slug}` },
        ]}
      />

      <article className="mx-auto max-w-3xl px-6 pb-32 pt-10 md:px-10">
        <Reveal>
          <span className="font-mono text-xs uppercase tracking-widest2 text-orange">{insight.category}</span>
          <h1 className="mt-4 text-balance font-display text-4xl text-warm md:text-5xl">{insight.title}</h1>
          <div className="mt-6 flex flex-wrap items-center gap-4 font-mono text-[11px] uppercase tracking-widest2 text-muted">
            <span>By {insight.author}</span>
            <span aria-hidden="true">·</span>
            <time dateTime={insight.publishedAt}>{formatDate(insight.publishedAt)}</time>
            <span aria-hidden="true">·</span>
            <span>{insight.readingTime}</span>
          </div>
        </Reveal>

        {insight.headings.length > 0 && (
          <Reveal delay={0.06}>
            <nav aria-label="Table of contents" className="mt-10 border border-line p-6">
              <span className="font-mono text-[10px] uppercase tracking-widest2 text-orange">
                On this page
              </span>
              <ul className="mt-3 flex flex-col gap-2">
                {insight.headings.map((heading) => (
                  <li key={heading.id} className={heading.depth === 3 ? "ml-4" : ""}>
                    <a href={`#${heading.id}`} className="text-sm text-muted hover:text-orange">
                      {heading.text}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </Reveal>
        )}

        <Reveal delay={0.1}>
          <div
            className="prose-gridkeep mt-10"
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: insight.contentHtml }}
          />
        </Reveal>

        {related.length > 0 && (
          <Reveal delay={0.14}>
            <div className="mt-20 border-t border-line pt-10">
              <span className="font-mono text-xs uppercase tracking-widest2 text-orange">Related insights</span>
              <ul className="mt-4 flex flex-col gap-3">
                {related.map((item) => (
                  <li key={item.slug}>
                    <Link href={`/insights/${item.slug}`} className="text-warm hover:text-orange">
                      {item.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        )}
      </article>
    </>
  );
}
