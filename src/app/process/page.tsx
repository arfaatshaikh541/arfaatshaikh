import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { processSteps } from "@/data/process";
import { PageHeader } from "@/components/ui/PageHeader";
import { CtaLink } from "@/components/ui/CtaLink";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbSchema } from "@/lib/schema";

export const metadata: Metadata = buildMetadata({
  title: "Process",
  description:
    "How an engagement with Arfaat Shaikh actually runs — discovery, scope and architecture, build, launch and handover, and a support window after launch.",
  path: "/process",
});

export default function ProcessPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Process", path: "/process" },
          ]),
        ]}
      />
      <PageHeader
        eyebrow="How It Runs"
        title="Process"
        description="No fixed template pretending every project is the same shape. This is the sequence that stays constant underneath it — how work actually moves from a conversation to something running in production."
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Process", href: "/process" },
        ]}
      />

      <section className="container-edge py-24 md:py-32" aria-labelledby="process-steps-heading">
        <h2 id="process-steps-heading" className="sr-only">
          Engagement steps
        </h2>
        <ol className="border-t border-[var(--color-line)]">
          {processSteps.map((step, index) => (
            <li key={step.title} className="border-b border-[var(--color-line)] py-10 md:py-14">
              <div className="grid gap-4 md:grid-cols-[100px_1fr] md:gap-8">
                <span className="font-mono text-sm text-[var(--color-blood-red)]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="max-w-2xl">
                  <h3 className="font-display text-2xl uppercase text-[var(--color-off-white)] md:text-3xl">
                    {step.title}
                  </h3>
                  <p className="mt-3 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                    {step.description}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="container-edge border-t border-[var(--color-line)] py-24 md:py-32" aria-labelledby="process-cta-heading">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Start a Project
        </p>
        <h2
          id="process-cta-heading"
          className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl"
        >
          Ready to start at step one?
        </h2>
        <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          Tell me about the problem you&apos;re trying to solve, and I&apos;ll give
          you an honest read on scope and fit.
        </p>
        <div className="mt-10">
          <CtaLink href="/contact">Start the conversation</CtaLink>
        </div>
      </section>
    </>
  );
}
