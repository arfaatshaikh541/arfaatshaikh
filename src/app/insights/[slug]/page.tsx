import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema, articleSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import { insights } from "@/data/insights";

interface InsightPageProps {
  params: { slug: string };
}

export function generateStaticParams() {
  return insights.map((a) => ({ slug: a.slug }));
}

export function generateMetadata({ params }: InsightPageProps): Metadata {
  const article = insights.find((a) => a.slug === params.slug);
  if (!article) return buildMetadata({ title: "Insight", path: `/insights/${params.slug}` });
  return buildMetadata({
    title: article.title,
    description: article.summary,
    path: `/insights/${article.slug}`,
  });
}

export default function InsightDetailPage({ params }: InsightPageProps) {
  const article = insights.find((a) => a.slug === params.slug);
  if (!article) notFound();

  const crumbs = [
    { name: "Home", path: "/" },
    { name: "Insights", path: "/insights" },
    { name: article.title, path: `/insights/${article.slug}` },
  ];

  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <JsonLd
        data={articleSchema({
          title: article.title,
          description: article.summary,
          path: `/insights/${article.slug}`,
          datePublished: article.date,
        })}
      />
      <Breadcrumbs items={crumbs} />

      <article className="border-b border-line bg-black py-16 md:py-24">
        <div className="mx-auto max-w-3xl px-6 md:px-10">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-orange-primary">{article.category}</span>
          <h1 className="gk-heading mt-4 text-3xl text-warmwhite sm:text-4xl md:text-5xl">{article.title}</h1>
          <div className="mt-5 flex items-center gap-4 font-mono text-[10px] uppercase tracking-[0.1em] text-muted">
            <time dateTime={article.date}>
              {new Date(article.date).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
            </time>
            <span aria-hidden="true">•</span>
            <span>{article.readTime}</span>
          </div>

          <div className="gk-divider my-10" />

          <div className="flex flex-col gap-6">
            {article.body.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed text-warmwhite/85 md:text-base">
                {paragraph}
              </p>
            ))}
          </div>

          <Link
            href="/insights"
            className="mt-12 inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.14em] text-orange-primary hover:text-orange-bright"
          >
            ← All Insights
          </Link>
        </div>
      </article>
    </>
  );
}
