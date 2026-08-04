import type { Metadata } from "next";
import { buildMetadata, siteConfig } from "@/lib/seo";
import { PageHeader } from "@/components/ui/PageHeader";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbSchema } from "@/lib/schema";

export const metadata: Metadata = buildMetadata({
  title: "Privacy Policy",
  description:
    "How Arfaat Shaikh and GRIDKEEP collect, use, and protect information submitted through this site, including the contact form.",
  path: "/privacy",
});

export default function PrivacyPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbSchema([
          { name: "Home", path: "/" },
          { name: "Privacy Policy", path: "/privacy" },
        ])}
      />
      <PageHeader
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Privacy Policy", href: "/privacy" },
        ]}
        eyebrow="Legal"
        title="Privacy Policy"
        description="This page explains what information this site collects, why, and how it is handled."
      />

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          What this site is
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            This site (arfaat.com) is the personal and professional portfolio
            of Arfaat Shaikh, Creative Engineer and founder of GRIDKEEP. This
            policy explains what information is collected when you use this
            site, why it&apos;s collected, and how it&apos;s handled.
          </p>
          <p>Last updated: 11 July 2026.</p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Information collected via the contact form
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            When you submit an enquiry through the contact form, the
            following information may be collected: your name, email
            address, company name, phone number, the service you&apos;re
            enquiring about, an approximate budget range, a description of
            your project, and your preferred method of contact.
          </p>
          <p>
            This information is used solely to understand your enquiry,
            respond to it, and, if you choose to proceed, to scope and deliver
            the work discussed. Fields marked optional are used only if you
            choose to provide them, to give a more useful reply.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          How information is used
        </h2>
        <div className="mt-6 max-w-3xl space-y-4 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>Information submitted through this site is used to:</p>
          <ul className="list-disc space-y-2 pl-6">
            <li>Respond to enquiries sent via the contact form.</li>
            <li>
              Understand and scope potential projects before any engagement
              begins.
            </li>
            <li>
              Maintain records relevant to an ongoing or completed
              engagement, where one proceeds.
            </li>
          </ul>
          <p>
            Information is not used for unrelated marketing, and is not sold
            to third parties under any circumstances.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Data retention
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            Enquiry information is retained only for as long as reasonably
            necessary to respond to your enquiry or, where an engagement
            proceeds, for the duration of that engagement and any period
            required afterward for legitimate business or legal record-keeping
            purposes. You can request deletion of your information at any
            time — see &quot;Your rights&quot; below.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Third-party sharing
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            Information submitted through this site is not shared with third
            parties beyond what is necessary to respond to your enquiry or
            deliver an agreed engagement (for example, tools used to send or
            receive email). No information is sold to third parties.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Cookies and analytics
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            This site may use privacy-respecting analytics to understand
            general traffic patterns, such as which pages are visited and how
            the site is performing. This helps improve the site over time. No
            information collected this way is sold to third parties, and
            analytics data is not combined with the personal information you
            submit via the contact form.
          </p>
          <p>
            If cookies are used, they are limited to what is reasonably
            necessary for the site to function and to understand aggregate
            usage — not for third-party advertising.
          </p>
        </div>
      </section>

      <section className="container-edge border-b border-[var(--color-line)] py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Your rights
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            You can request access to, correction of, or deletion of any
            personal information you&apos;ve submitted through this site at
            any time. To make a request, email{" "}
            <a
              href={`mailto:${siteConfig.email}`}
              className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              {siteConfig.email}
            </a>{" "}
            and the request will be handled as promptly as possible.
          </p>
        </div>
      </section>

      <section className="container-edge py-24 md:py-32">
        <h2 className="font-display text-3xl uppercase text-[var(--color-off-white)] md:text-4xl">
          Questions about this policy
        </h2>
        <div className="mt-6 max-w-3xl space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            If you have any questions about this privacy policy or how your
            information is handled, contact{" "}
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
