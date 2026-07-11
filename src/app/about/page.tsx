import type { Metadata } from "next";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { Reveal } from "@/components/ui/Reveal";
import { ButtonLink } from "@/components/ui/Button";
import { buildMetadata } from "@/lib/seo";
import { webPageSchema } from "@/lib/schema";
import { FOUNDER_NAME, LOCATION } from "@/lib/constants";

export const metadata: Metadata = buildMetadata({
  title: "About GRIDKEEP",
  description:
    "GRIDKEEP is a founder-led technology systems company based in the United Arab Emirates, founded by Arfaat Shaikh.",
  path: "/about",
});

export default function AboutPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "About GRIDKEEP",
          description: "GRIDKEEP is a founder-led technology systems company based in the UAE.",
          path: "/about",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "About", path: "/about" }]} />
      <PageHero
        eyebrow="About"
        title="A founder-led technology systems company."
        description={`GRIDKEEP was founded by ${FOUNDER_NAME} and is based in ${LOCATION}. It exists to close the gap between technical execution and business outcomes.`}
      />

      <section className="mx-auto max-w-3xl px-6 pb-32 md:px-10">
        <Reveal>
          <h2 className="font-display text-2xl text-warm">Why GRIDKEEP exists</h2>
          <p className="mt-4 text-muted">
            Most technology work fails not because the engineering is weak, but because it
            never connects back to what the business actually needs to happen next. GRIDKEEP
            was built to close that gap directly — one point of accountability, from
            architecture through delivery, instead of a chain of handoffs between sales,
            account management, and the engineers doing the work.
          </p>
        </Reveal>

        <Reveal delay={0.05}>
          <h2 className="mt-14 font-display text-2xl text-warm">Founder-led, by design</h2>
          <p className="mt-4 text-muted">
            {FOUNDER_NAME} founded GRIDKEEP on a technical foundation in Computer Science,
            paired with commercial experience built through direct customer service and
            sales work. That combination shapes how GRIDKEEP operates: every system is
            designed with an understanding of how it will actually be sold, adopted, and
            used — not just how it will be built.
          </p>
          <p className="mt-4 text-muted">
            GRIDKEEP is intentionally founder-led rather than structured around a large
            delivery team. Engagements stay direct, and the person responsible for the
            outcome is reachable throughout the project, not insulated behind account
            management layers.
          </p>
        </Reveal>

        <Reveal delay={0.1}>
          <h2 className="mt-14 font-display text-2xl text-warm">What GRIDKEEP builds</h2>
          <p className="mt-4 text-muted">
            GRIDKEEP designs and engineers AI and AI agents, business automation, custom
            software and SaaS platforms, cybersecurity architecture, cloud infrastructure and
            DevOps, CRM and ERP systems, API integrations, data dashboards, and immersive web
            experiences — treated as connected systems rather than one-off deliverables.
          </p>
        </Reveal>

        <Reveal delay={0.15}>
          <h2 className="mt-14 font-display text-2xl text-warm">Based in the UAE</h2>
          <p className="mt-4 text-muted">
            GRIDKEEP operates from the United Arab Emirates, working with businesses across
            the region and beyond that need infrastructure-grade technology work, not
            template solutions.
          </p>
        </Reveal>

        <Reveal delay={0.2}>
          <div className="mt-14">
            <ButtonLink href="/contact">Start a conversation</ButtonLink>
          </div>
        </Reveal>
      </section>
    </>
  );
}
