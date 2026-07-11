import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata } from "@/lib/seo";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { personSchema, profilePageSchema, breadcrumbSchema } from "@/lib/schema";

export const metadata: Metadata = buildMetadata({
  title: "About",
  description:
    "Arfaat Shaikh is a Creative Engineer in the United Arab Emirates and founder of GRIDKEEP, combining a Computer Science background with an early career in customer service and sales.",
  path: "/about",
});

const FOCUS_AREAS = [
  "AI agents",
  "Automation",
  "Custom software",
  "SaaS",
  "Web development",
  "Immersive web experiences",
  "Cybersecurity",
  "Cloud & DevOps",
  "CRM / ERP / API integrations",
  "UI/UX & digital strategy",
];

const APPROACH = [
  {
    title: "Start with the business, not the brief",
    description:
      "Before any technical decision is made, I try to understand what the business is actually trying to achieve — what the request is standing in for, not just what it literally asks for.",
  },
  {
    title: "Build for what's real",
    description:
      "Systems are scoped to the actual problem in front of them. No speculative features, no over-engineering for a scale that doesn't exist yet.",
  },
  {
    title: "Security and structure from day one",
    description:
      "Access control, data handling, and sound architecture are part of the build from the start, not something bolted on after launch.",
  },
  {
    title: "Keep systems visible",
    description:
      "Whether it's an AI agent or an automation pipeline, I build so you can see what the system is doing and why, rather than trusting a black box.",
  },
];

export default function AboutPage() {
  return (
    <>
      <JsonLd
        data={[
          personSchema(),
          profilePageSchema(),
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "About", path: "/about" },
          ]),
        ]}
      />
      <PageHeader
        crumbs={[
          { name: "Home", href: "/" },
          { name: "About", href: "/about" },
        ]}
        eyebrow="About"
        title="Arfaat Shaikh"
        description="Creative Engineer based in the United Arab Emirates, and founder of GRIDKEEP."
      />

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Background
        </p>
        <h2 className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          An unusual path into engineering
        </h2>
        <div className="mt-8 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            I hold a Bachelor&apos;s degree in Computer Science, but my career
            didn&apos;t start in engineering. I started out in customer
            service and sales, working directly with people and businesses
            before ever writing production code.
          </p>
          <p>
            That background shapes how I work today. Having sat on the
            commercial side of a business, I don&apos;t just design systems
            to satisfy a technical requirement as it&apos;s written down — I
            design them with the business&apos;s real, underlying goals in
            mind: what actually needs to happen for the business to move
            forward, and what a customer on the other end of the system
            actually experiences.
          </p>
          <p>
            That combination of technical depth and commercial and customer
            understanding is the throughline across everything I build, from
            AI agents to full software platforms.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Founder, GRIDKEEP
        </p>
        <h2 className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          The studio behind the work
        </h2>
        <div className="mt-8 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            I&apos;m the founder of{" "}
            <Link
              href="/gridkeep"
              className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              GRIDKEEP
            </Link>
            , a founder-led technology studio. GRIDKEEP is the practice
            through which the engineering, design, and strategy work
            described on this site is delivered.
          </p>
          <p>
            You can read more about the studio at{" "}
            <Link
              href="/gridkeep"
              className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              /gridkeep
            </Link>{" "}
            or directly at{" "}
            <a
              href="https://gridkeep.com"
              className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              gridkeep.com
            </a>
            .
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Focus Areas
        </p>
        <h2 className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          What I work on
        </h2>
        <ul className="mt-10 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-2 lg:grid-cols-3">
          {FOCUS_AREAS.map((area) => (
            <li
              key={area}
              className="bg-black p-6 font-mono text-sm uppercase tracking-[0.1em] text-[var(--color-off-white)]"
            >
              {area}
            </li>
          ))}
        </ul>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Approach
        </p>
        <h2 className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          How I work
        </h2>
        <div className="mt-16 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-2">
          {APPROACH.map((item, index) => (
            <div key={item.title} className="bg-black p-8">
              <span className="font-mono text-xs text-[var(--color-blood-red)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3 className="mt-3 font-display text-xl uppercase text-[var(--color-off-white)]">
                {item.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">
                {item.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="container-edge py-24 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Start a Project
        </p>
        <h2 className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl">
          Want to talk about what you&apos;re building?
        </h2>
        <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          Tell me about the problem you&apos;re trying to solve, and I&apos;ll
          give you an honest read on scope and fit.
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
