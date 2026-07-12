import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import { INSIGHTS, getInsightBySlug } from "@/lib/insights-data";
import { articleSchema } from "@/lib/schema";

export function generateStaticParams() {
  return INSIGHTS.map((i) => ({ slug: i.slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const insight = getInsightBySlug(slug);
  if (!insight) return {};
  return {
    title: insight.title,
    description: insight.excerpt,
    alternates: { canonical: `/insights/${insight.slug}` },
    openGraph: {
      url: `/insights/${insight.slug}`,
      title: insight.title,
      description: insight.excerpt,
      type: "article",
      publishedTime: insight.datePublished,
    },
  };
}

export default async function InsightPage({ params }: Props) {
  const { slug } = await params;
  const insight = getInsightBySlug(slug);
  if (!insight) notFound();

  return (
    <>
      <JsonLd
        data={articleSchema({
          headline: insight.title,
          description: insight.excerpt,
          path: `/insights/${insight.slug}`,
          datePublished: insight.datePublished,
        })}
      />
      <Breadcrumbs
        items={[
          { name: "Home", path: "/" },
          { name: "Insights", path: "/insights" },
          { name: insight.title, path: `/insights/${insight.slug}` },
        ]}
      />

      <article className="bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-3xl">
          <span className="font-mono-tech text-[0.7rem] uppercase tracking-[0.14em] text-gk-orange">
            {new Date(insight.datePublished).toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" })} ·{" "}
            {insight.readingTime}
          </span>
          <h1 className="font-display mt-4 text-4xl font-bold uppercase leading-tight sm:text-5xl">{insight.title}</h1>
          <div className="mt-10 space-y-6">
            {insight.body.map((paragraph, i) => (
              <p key={i} className="text-base leading-relaxed text-gk-grey">
                {paragraph}
              </p>
            ))}
          </div>
          <div className="mt-14 border-t border-gk-graphite pt-8">
            <Link href="/insights" className="gk-btn gk-btn-ghost">
              All Insights
            </Link>
          </div>
        </div>
      </article>
    </>
  );
}
