import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { techStackGroups } from "@/data/techStack";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbSchema } from "@/lib/schema";

export const metadata: Metadata = buildMetadata({
  title: "Tech Stack",
  description:
    "The languages, frameworks, and infrastructure Arfaat Shaikh builds with — TypeScript and Next.js, AI model APIs, PostgreSQL, cloud and DevOps tooling, and Three.js for real-time 3D work.",
  path: "/tech-stack",
});

export default function TechStackPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Tech Stack", path: "/tech-stack" },
          ]),
        ]}
      />
      <PageHeader
        eyebrow="Toolset"
        title="Tech Stack"
        description="The tools chosen for a job, not a resume. What shows up here is what's actually running in production across these projects."
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Tech Stack", href: "/tech-stack" },
        ]}
      />

      <section className="container-edge py-24 md:py-32" aria-labelledby="stack-list-heading">
        <h2 id="stack-list-heading" className="sr-only">
          Full technology stack by category
        </h2>
        <div className="grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] md:grid-cols-2">
          {techStackGroups.map((group, index) => (
            <div key={group.label} className="bg-black p-8 md:p-10">
              <span className="font-mono text-xs text-[var(--color-blood-red)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3 className="mt-3 font-display text-2xl uppercase text-[var(--color-off-white)] md:text-3xl">
                {group.label}
              </h3>
              <p className="mt-3 max-w-md text-sm leading-relaxed text-[var(--color-muted)]">
                {group.description}
              </p>
              <ul className="mt-6 flex flex-wrap gap-2">
                {group.items.map((item) => (
                  <li
                    key={item}
                    className="border border-[var(--color-line)] px-4 py-2 font-mono text-[0.65rem] uppercase tracking-[0.08em] text-[var(--color-off-white)]"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="container-edge border-t border-[var(--color-line)] py-24 md:py-32" aria-labelledby="stack-cta-heading">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Start a Project
        </p>
        <h2
          id="stack-cta-heading"
          className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl"
        >
          Have a stack you&apos;re already committed to?
        </h2>
        <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          I work inside existing codebases and infrastructure as often as I
          start from scratch. Tell me what you&apos;re on and I&apos;ll tell you
          honestly whether it&apos;s a fit.
        </p>
        <div className="mt-10">
          <CtaLink href="/contact">Start the conversation</CtaLink>
        </div>
      </section>
    </>
  );
}
