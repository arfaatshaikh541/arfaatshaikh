import type { Metadata } from "next";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { buildMetadata } from "@/lib/seo";
import { webPageSchema } from "@/lib/schema";
import { CONTACT_EMAIL } from "@/lib/constants";

export const metadata: Metadata = buildMetadata({
  title: "Privacy Policy",
  description: "How GRIDKEEP collects, uses, and protects information submitted through this website.",
  path: "/privacy",
});

export default function PrivacyPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "Privacy Policy",
          description: "How GRIDKEEP handles information submitted through this website.",
          path: "/privacy",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Privacy Policy", path: "/privacy" }]} />
      <PageHero
        eyebrow="Legal"
        title="Privacy Policy"
        description="This policy explains what information GRIDKEEP collects through this website and how it is used."
      />

      <section className="prose-gridkeep mx-auto max-w-3xl px-6 pb-32 md:px-10">
        <h2>Information we collect</h2>
        <p>
          When you submit the contact form on this website, GRIDKEEP collects the information
          you provide directly — including your name, work email, company, phone number,
          service interest, budget range, and project description. GRIDKEEP does not collect
          personal information through this website beyond what you submit voluntarily.
        </p>

        <h2>How we use your information</h2>
        <p>
          Information submitted through the contact form is used solely to respond to your
          inquiry and evaluate a potential project. It is not sold, rented, or shared with
          third parties for marketing purposes.
        </p>

        <h2>Data storage and security</h2>
        <p>
          Submitted information is transmitted securely and retained only as long as needed
          to respond to your inquiry or, if a project proceeds, for the duration of that
          engagement and any legally required retention period afterward.
        </p>

        <h2>Cookies and analytics</h2>
        <p>
          This website does not use third-party advertising cookies. Any analytics used are
          limited to understanding aggregate site performance and do not track individuals
          across other websites.
        </p>

        <h2>Your rights</h2>
        <p>
          You may request access to, correction of, or deletion of any information you have
          submitted to GRIDKEEP by contacting {CONTACT_EMAIL}.
        </p>

        <h2>Changes to this policy</h2>
        <p>
          This policy may be updated as the website evolves. The date of the most recent
          update will be reflected on this page.
        </p>

        <h2>Contact</h2>
        <p>
          Questions about this policy can be directed to{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </section>
    </>
  );
}
