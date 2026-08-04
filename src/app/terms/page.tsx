import type { Metadata } from "next";
import { buildMetadata, siteConfig } from "@/lib/seo";
import { PageHeader } from "@/components/ui/PageHeader";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbSchema } from "@/lib/schema";

export const metadata: Metadata = buildMetadata({
  title: "Terms & Conditions",
  description:
    "The terms and conditions governing use of this site and engagement of services from Arfaat Shaikh and GRIDKEEP.",
  path: "/terms",
});

export default function TermsPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbSchema([
          { name: "Home", path: "/" },
          { name: "Terms & Conditions", path: "/terms" },
        ])}
      />
      <PageHeader
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Terms & Conditions", href: "/terms" },
        ]}
        eyebrow="Legal"
        title="Terms & Conditions"
        description="The terms that apply to using this site and engaging services through it."
      />

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Acceptance of terms
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            By accessing or using this site (arfaat.com), you agree to these
            terms and conditions. If you do not agree with any part of these
            terms, please do not use this site.
          </p>
          <p>Last updated: 11 July 2026.</p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Description of services
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            This site presents the engineering, design, and consulting
            services offered by Arfaat Shaikh and GRIDKEEP, spanning AI
            agents, automation, custom software, SaaS, web development,
            immersive web experiences, cybersecurity, cloud & DevOps, CRM/ERP
            and API integrations, UI/UX, and digital strategy.
          </p>
          <p>
            This site is not an e-commerce platform. Services are not sold or
            checked out through this site — engagements begin with a
            conversation, as described below.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Engagement process
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            There is no fixed, published pricing for services offered through
            this site, because scope varies significantly from project to
            project. Enquiries submitted via the contact form lead to a
            scoping conversation, after which pricing, timeline, and
            deliverables are agreed directly between the parties, typically
            in a separate written agreement or proposal specific to that
            engagement.
          </p>
          <p>
            Nothing on this site constitutes a binding offer to perform work
            at any specific price or timeline. Any such terms are only
            binding once agreed in writing for a specific engagement.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Intellectual property
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            The content of this site — including its design, text, code, and
            visual identity — is the property of Arfaat Shaikh and GRIDKEEP,
            unless otherwise credited, and may not be reproduced without
            permission.
          </p>
          <p>
            For client engagements, unless otherwise agreed in a signed
            contract, full ownership of the source code and deliverables
            produced for that engagement transfers to the client upon final
            payment. Pre-existing tools, frameworks, and internal utilities
            used to deliver the work remain the property of Arfaat Shaikh and
            GRIDKEEP and are licensed for the client&apos;s use as part of the
            deliverable.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Limitation of liability
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            This site and its content are provided on an &quot;as is&quot;
            basis, without warranties of any kind, express or implied. To the
            fullest extent permitted by law, Arfaat Shaikh and GRIDKEEP are
            not liable for any indirect, incidental, or consequential damages
            arising from use of this site.
          </p>
          <p>
            For specific engagements, liability is governed by the terms
            agreed in the relevant written contract for that engagement,
            which takes precedence over this general statement.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Governing law
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            These terms are governed by the laws of the United Arab Emirates,
            without regard to conflict of law principles.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Changes to these terms
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            These terms may be updated from time to time to reflect changes
            to the services offered or for legal or operational reasons. The
            &quot;last updated&quot; date at the top of this page reflects the
            most recent revision. Continued use of this site after changes
            are posted constitutes acceptance of the updated terms.
          </p>
        </div>
      </section>

      <section className="container-edge py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Contact
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            Questions about these terms can be sent to{" "}
            <a
              href={`mailto:${siteConfig.email}`}
              className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              {siteConfig.email}
            </a>
            .
          </p>
        </div>
      </section>
    </>
  );
}
