import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { buildMetadata } from "@/lib/seo";
import { articles, getArticleBySlug, getReadingTime } from "@/data/insights";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { articleSchema, breadcrumbSchema, faqSchema } from "@/lib/schema";
import { formatDate } from "@/lib/utils";

interface ArticlePageParams {
  params: Promise<{ slug: string }>;
}

export default async function ArticlePage({ params }: ArticlePageParams) {
  const { slug } = await params;
  const article = getArticleBySlug(slug);

  if (!article) {
    notFound();
  }

  const readingTime = getReadingTime(article);
  const wasModified = article.modifiedAt !== article.publishedAt;
  const relatedArticles = article.relatedSlugs
    .map((relatedSlug) => getArticleBySlug(relatedSlug))
    .filter((related): related is NonNullable<typeof related> => Boolean(related));

  return (
    <>
      <JsonLd
        data={[
          articleSchema(article),
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Insights", path: "/insights" },
            { name: article.title, path: `/insights/${article.slug}` },
          ]),
        ]}
      />

      <PageHeader
        eyebrow={article.category}
        title={article.title}
        description={article.excerpt}
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Insights", href: "/insights" },
          { name: article.title, href: `/insights/${article.slug}` },
        ]}
      />

      <section className="container-edge border-b border-[var(--color-line)] py-8">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 font-mono text-xs uppercase tracking-[0.1em] text-[var(--color-muted)]">
          <span>
            By <span className="text-[var(--color-off-white)]">{article.author}</span>
          </span>
          <span aria-hidden="true">/</span>
          <span>Published {formatDate(article.publishedAt)}</span>
          {wasModified && (
            <>
              <span aria-hidden="true">/</span>
              <span>Updated {formatDate(article.modifiedAt)}</span>
            </>
          )}
          <span aria-hidden="true">/</span>
          <span>{readingTime} min read</span>
        </div>

        {article.tags.length > 0 && (
          <ul className="mt-6 flex flex-wrap gap-2">
            {article.tags.map((tag) => (
              <li
                key={tag}
                className="border border-[var(--color-line)] px-4 py-2 font-mono text-[0.65rem] uppercase tracking-[0.08em] text-[var(--color-off-white)]"
              >
                {tag}
              </li>
            ))}
          </ul>
        )}
      </section>

      <nav
        aria-labelledby="toc-heading"
        className="container-edge border-b border-[var(--color-line)] py-12"
      >
        <p
          id="toc-heading"
          className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]"
        >
          Contents
        </p>
        <ol className="mt-6 max-w-3xl space-y-3">
          {article.sections.map((section, index) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className="group flex items-baseline gap-3 font-mono text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-off-white)]"
              >
                <span className="text-[var(--color-muted)]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="group-hover:text-[var(--color-blood-red)]">
                  {section.heading}
                </span>
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className={article.faqs && article.faqs.length > 0 ? "" : "border-b border-[var(--color-line)]"}>
        {article.sections.map((section) => (
          <section key={section.id} id={section.id} className="container-edge max-w-3xl py-12">
            <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
              {section.heading}
            </h2>
            <div className="mt-6 space-y-5">
              {section.paragraphs.map((paragraph, paragraphIndex) => (
                <p
                  key={paragraphIndex}
                  className="text-base leading-relaxed text-[var(--color-muted)] md:text-lg"
                >
                  {paragraph}
                </p>
              ))}
            </div>
            {section.list && section.list.length > 0 && (
              <ul className="mt-6 space-y-3 border-l border-[var(--color-line)] pl-6">
                {section.list.map((item, itemIndex) => (
                  <li
                    key={itemIndex}
                    className="text-base leading-relaxed text-[var(--color-off-white)] md:text-lg"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>

      {article.faqs && article.faqs.length > 0 && (
        <>
          <JsonLd data={faqSchema(article.faqs)} />
          <section
            className="container-edge border-b border-[var(--color-line)] py-24 md:py-32"
            aria-labelledby="faq-heading"
          >
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
              Questions
            </p>
            <h2
              id="faq-heading"
              className="mt-4 font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl"
            >
              Frequently Asked Questions
            </h2>
            <div className="mt-10 max-w-3xl border-t border-[var(--color-line)]">
              {article.faqs.map((faq) => (
                <details
                  key={faq.question}
                  className="group border-b border-[var(--color-line)] py-6"
                >
                  <summary className="cursor-pointer list-none font-display text-lg uppercase tracking-wide text-[var(--color-off-white)] transition-colors group-open:text-[var(--color-blood-red)] md:text-xl">
                    {faq.question}
                  </summary>
                  <p className="mt-4 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                    {faq.answer}
                  </p>
                </details>
              ))}
            </div>
          </section>
        </>
      )}

      {relatedArticles.length > 0 && (
        <section
          className="container-edge border-b border-[var(--color-line)] py-24 md:py-32"
          aria-labelledby="related-heading"
        >
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Continue Reading
          </p>
          <h2
            id="related-heading"
            className="mt-4 font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl"
          >
            Related Articles
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-px border border-[var(--color-line)] bg-[var(--color-line)] md:grid-cols-2">
            {relatedArticles.map((related) => (
              <Link
                key={related.slug}
                href={`/insights/${related.slug}`}
                className="group bg-black p-8 transition-colors hover:bg-[var(--color-surface)]"
              >
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
                  {related.category}
                </p>
                <h3 className="mt-3 font-display text-2xl uppercase text-[var(--color-off-white)] transition-colors group-hover:text-[var(--color-blood-red)] md:text-3xl">
                  {related.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)] md:text-base">
                  {related.excerpt}
                </p>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="py-24 md:py-40" aria-labelledby="insights-cta-heading">
        <div className="container-edge">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Start a Project
          </p>
          <h2
            id="insights-cta-heading"
            className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl"
          >
            Have a problem like this one?
          </h2>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
            Tell me what you&apos;re trying to solve and I&apos;ll tell you honestly
            what it actually needs.
          </p>
          <div className="mt-10">
            <CtaLink href="/contact">Start the conversation</CtaLink>
          </div>
        </div>
      </section>
    </>
  );
}

export async function generateMetadata({ params }: ArticlePageParams): Promise<Metadata> {
  const { slug } = await params;
  const article = getArticleBySlug(slug);

  if (!article) {
    return {};
  }

  return buildMetadata({
    title: article.title,
    description: article.description,
    path: `/insights/${slug}`,
    type: "article",
  });
}

export function generateStaticParams() {
  return articles.map((article) => ({ slug: article.slug }));
}
