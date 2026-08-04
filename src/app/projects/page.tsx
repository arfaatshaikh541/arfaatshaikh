import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata } from "@/lib/seo";
import { projects } from "@/data/projects";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbSchema } from "@/lib/schema";

export const metadata: Metadata = buildMetadata({
  title: "Projects",
  description:
    "Real, founder-led work across client platforms, internal products, and early-stage concepts — built by Arfaat Shaikh and GRIDKEEP.",
  path: "/projects",
});

export default function ProjectsPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Projects", path: "/projects" },
          ]),
        ]}
      />
      <PageHeader
        eyebrow="Selected Work"
        title="Projects"
        description="A small, honest set of real projects — client platforms, internal products, and concepts still taking shape. No inflated case studies, just what's actually been built and what's in progress."
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Projects", href: "/projects" },
        ]}
      />

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="projects-list-heading">
        <h2 id="projects-list-heading" className="sr-only">
          Full list of projects
        </h2>
        <ul className="border-t border-[var(--color-line)]">
          {projects.map((project, index) => (
            <li key={project.slug} className="border-b border-[var(--color-line)]">
              <Link
                href={`/projects/${project.slug}`}
                className="group grid grid-cols-1 gap-6 py-10 transition-colors hover:bg-[var(--color-surface)] md:grid-cols-[80px_1fr_auto] md:gap-8 md:py-14"
              >
                <span className="font-mono text-sm text-[var(--color-muted)]">
                  {String(index + 1).padStart(2, "0")}
                </span>

                <div className="max-w-3xl">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--color-blood-red)]">
                      {project.status}
                    </span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--color-muted)]">
                      {project.year}
                    </span>
                  </div>
                  <h3 className="mt-3 font-display text-3xl uppercase text-[var(--color-off-white)] transition-colors group-hover:text-[var(--color-blood-red)] md:text-4xl">
                    {project.title}
                  </h3>
                  <p className="mt-2 font-mono text-xs uppercase tracking-[0.08em] text-[var(--color-muted)]">
                    {project.category}
                  </p>
                  <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[var(--color-muted)] md:text-base">
                    {project.summary}
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

      <section className="py-24 md:py-40" aria-labelledby="projects-cta-heading">
        <div className="container-edge">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Start a Project
          </p>
          <h2
            id="projects-cta-heading"
            className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl"
          >
            Have something worth building properly?
          </h2>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
            Tell me about the problem you&apos;re trying to solve, and
            I&apos;ll give you an honest read on scope and fit.
          </p>
          <div className="mt-10">
            <CtaLink href="/contact">Start the conversation</CtaLink>
          </div>
        </div>
      </section>
    </>
  );
}
