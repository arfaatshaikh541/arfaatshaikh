import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { buildMetadata } from "@/lib/seo";
import { projects, getProjectBySlug } from "@/data/projects";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { creativeWorkSchema, breadcrumbSchema } from "@/lib/schema";

export function generateStaticParams() {
  return projects.map((project) => ({ slug: project.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const project = getProjectBySlug(slug);
  if (!project) return {};

  return buildMetadata({
    title: project.title,
    description: project.summary,
    path: `/projects/${slug}`,
  });
}

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const project = getProjectBySlug(slug);
  if (!project) notFound();

  const otherProjects = projects.filter((p) => p.slug !== project.slug);

  const specs = [
    { label: "Status", value: project.status },
    { label: "Year", value: project.year },
    { label: "Role", value: project.role },
    { label: "Industry", value: project.industry },
  ];

  return (
    <>
      <JsonLd
        data={[
          creativeWorkSchema(project),
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Projects", path: "/projects" },
            { name: project.title, path: `/projects/${project.slug}` },
          ]),
        ]}
      />
      <PageHeader
        eyebrow={project.category}
        title={project.title}
        description={project.summary}
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Projects", href: "/projects" },
          { name: project.title, href: `/projects/${project.slug}` },
        ]}
      />

      <section
        className="container-edge border-b border-[var(--color-line)] py-16 md:py-20"
        aria-labelledby="project-spec-heading"
      >
        <h2 id="project-spec-heading" className="sr-only">
          Project details
        </h2>
        <div className="grid grid-cols-1 gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-2 lg:grid-cols-4">
          {specs.map((spec) => (
            <div key={spec.label} className="bg-black p-6">
              <p className="font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-muted)]">
                {spec.label}
              </p>
              <p className="mt-2 font-display text-xl uppercase text-[var(--color-off-white)]">
                {spec.value}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section
        className="container-edge border-b border-[var(--color-line)] py-24 md:py-32"
        aria-labelledby="project-overview-heading"
      >
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Overview
        </p>
        <h2
          id="project-overview-heading"
          className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl"
        >
          {project.title}
        </h2>
        <div className="mt-8 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          {project.description.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
      </section>

      <section
        className="container-edge border-b border-[var(--color-line)] py-24 md:py-32"
        aria-labelledby="project-capabilities-heading"
      >
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Capabilities
        </p>
        <h2
          id="project-capabilities-heading"
          className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl"
        >
          What was involved
        </h2>
        <ul className="mt-10 flex flex-wrap gap-3">
          {project.capabilities.map((item) => (
            <li
              key={item}
              className="border border-[var(--color-line)] px-5 py-3 font-mono text-xs uppercase tracking-[0.08em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
            >
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section
        className="container-edge border-b border-[var(--color-line)] py-24 md:py-32"
        aria-labelledby="project-technologies-heading"
      >
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Stack
        </p>
        <h2
          id="project-technologies-heading"
          className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl"
        >
          Technologies
        </h2>
        <ul className="mt-10 flex flex-wrap gap-3">
          {project.technologies.map((item) => (
            <li
              key={item}
              className="border border-[var(--color-line)] px-5 py-3 font-mono text-xs uppercase tracking-[0.08em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
            >
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section
        className="container-edge border-b border-[var(--color-line)] py-24 md:py-32"
        aria-labelledby="project-highlights-heading"
      >
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Key Points
        </p>
        <h2
          id="project-highlights-heading"
          className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl"
        >
          Highlights
        </h2>
        <ul className="mt-10 max-w-3xl space-y-6 border-t border-[var(--color-line)]">
          {project.highlights.map((item, index) => (
            <li
              key={index}
              className="flex gap-6 border-b border-[var(--color-line)] pb-6 pt-6 first:pt-0"
            >
              <span className="font-mono text-xs text-[var(--color-blood-red)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <p className="text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                {item}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section
        className="container-edge border-b border-[var(--color-line)] py-24 md:py-32"
        aria-labelledby="more-projects-heading"
      >
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Keep Browsing
        </p>
        <h2
          id="more-projects-heading"
          className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl"
        >
          More Projects
        </h2>
        <div className="mt-12 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] md:grid-cols-2">
          {otherProjects.map((other) => (
            <Link
              key={other.slug}
              href={`/projects/${other.slug}`}
              className="group flex flex-col justify-between bg-black p-8 transition-colors hover:bg-[var(--color-surface)]"
            >
              <div>
                <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--color-blood-red)]">
                  {other.status}
                </span>
                <h3 className="mt-4 font-display text-2xl uppercase leading-tight text-[var(--color-off-white)]">
                  {other.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">
                  {other.summary}
                </p>
              </div>
              <span
                aria-hidden="true"
                className="mt-8 inline-block font-mono text-sm text-[var(--color-muted)] transition-transform group-hover:translate-x-1 group-hover:text-[var(--color-blood-red)]"
              >
                View project →
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className="py-24 md:py-40" aria-labelledby="project-cta-heading">
        <div className="container-edge">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Start a Project
          </p>
          <h2
            id="project-cta-heading"
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
