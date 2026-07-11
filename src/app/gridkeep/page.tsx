import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, siteConfig } from "@/lib/seo";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { organizationSchema, breadcrumbSchema } from "@/lib/schema";
import { services } from "@/data/services";

export const metadata: Metadata = buildMetadata({
  title: "GRIDKEEP",
  description:
    "GRIDKEEP is a founder-led technology studio spanning AI, AI agents, automation, custom software, SaaS, cybersecurity, cloud infrastructure, DevOps, and immersive web experiences.",
  path: "/gridkeep",
});

const REASONS = [
  {
    title: "Founder-led",
    description:
      "GRIDKEEP is led directly by its founder. That means direct accountability for the work — no account manager layer between you and the person responsible for the outcome.",
  },
  {
    title: "One team, every discipline",
    description:
      "Instead of piecing a project across a design agency, a dev shop, a security consultant, and a cloud contractor, GRIDKEEP brings AI, software, security, and infrastructure work under one roof.",
  },
  {
    title: "One engineering standard",
    description:
      "The same standard of architecture, security, and craft is applied whether the work is an AI agent, a client platform, or the cloud infrastructure underneath it.",
  },
];

export default function GridkeepPage() {
  return (
    <>
      <JsonLd
        data={[
          organizationSchema(),
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "GRIDKEEP", path: "/gridkeep" },
          ]),
        ]}
      />
      <PageHeader
        crumbs={[
          { name: "Home", href: "/" },
          { name: "GRIDKEEP", href: "/gridkeep" },
        ]}
        eyebrow="Founder-Led Technology Studio"
        title="GRIDKEEP"
        description="A founder-led technology studio spanning AI, automation, custom software, cybersecurity, cloud infrastructure, and immersive web experiences."
      />

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          What GRIDKEEP Is
        </p>
        <h2 className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          One accountable partner, not a pile of vendors
        </h2>
        <div className="mt-8 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            GRIDKEEP is a founder-led technology studio, founded by Arfaat
            Shaikh, working across AI, AI agents, automation, custom
            software, SaaS, cybersecurity, cloud infrastructure, DevOps, and
            immersive web experiences.
          </p>
          <p>
            It exists to give businesses one accountable partner for the
            systems they depend on, instead of piecing that work together
            across disconnected vendors — a design agency here, a
            development shop there, a security consultant somewhere else,
            each with their own priorities and none fully accountable for
            how the pieces fit together.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Why GRIDKEEP
        </p>
        <h2 className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          Positioning
        </h2>
        <div className="mt-16 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-3">
          {REASONS.map((reason, index) => (
            <div key={reason.title} className="bg-black p-8">
              <span className="font-mono text-xs text-[var(--color-blood-red)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3 className="mt-3 font-display text-xl uppercase text-[var(--color-off-white)]">
                {reason.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">
                {reason.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Disciplines
        </p>
        <h2 className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          What GRIDKEEP works across
        </h2>
        <ul className="mt-10 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-2">
          {services.map((service) => (
            <li key={service.slug} className="bg-black p-8">
              <Link
                href={`/services/${service.slug}`}
                className="group inline-flex flex-col gap-2"
              >
                <h3 className="font-display text-xl uppercase text-[var(--color-off-white)] transition-colors group-hover:text-[var(--color-blood-red)]">
                  {service.name} →
                </h3>
                <p className="text-sm leading-relaxed text-[var(--color-muted)]">
                  {service.tagline}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Case Study
        </p>
        <h2 className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          GRIDKEEP Digital Experience
        </h2>
        <p className="mt-6 max-w-3xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          GRIDKEEP&apos;s own digital presence is built to the same standard
          applied to client work — an engineered, cinematic experience rather
          than a generic studio template, demonstrating the studio&apos;s
          technical capability through its own site.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <CtaLink href="/projects/gridkeep-digital-experience" variant="ghost">
            View the project
          </CtaLink>
          <a
            href={siteConfig.gridkeepUrl}
            className="inline-flex items-center gap-3 border border-[var(--color-line)] px-6 py-3 font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
          >
            Visit gridkeep.com ↗
          </a>
        </div>
      </section>

      <section className="container-edge py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Start a Project
        </p>
        <h2 className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl">
          Bring your systems under one accountable team
        </h2>
        <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          Tell me about the problem, not just the tool you think you need.
          I&apos;ll reply with an honest read on scope and whether it&apos;s a
          fit.
        </p>
        <div className="mt-10">
          <CtaLink href="/contact" variant="primary">
            Start a project
          </CtaLink>
        </div>
      </section>
    </>
  );
}
