import type { Metadata } from "next";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { buildMetadata } from "@/lib/seo";
import { webPageSchema } from "@/lib/schema";
import { CONTACT_EMAIL, SITE_NAME } from "@/lib/constants";

export const metadata: Metadata = buildMetadata({
  title: "Terms of Service",
  description: "The terms governing use of the GRIDKEEP website.",
  path: "/terms",
});

export default function TermsPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "Terms of Service",
          description: "The terms governing use of the GRIDKEEP website.",
          path: "/terms",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Terms of Service", path: "/terms" }]} />
      <PageHero
        eyebrow="Legal"
        title="Terms of Service"
        description="These terms govern your use of the GRIDKEEP website. Project-specific engagements are governed by a separate written agreement."
      />

      <section className="prose-gridkeep mx-auto max-w-3xl px-6 pb-32 md:px-10">
        <h2>Use of this website</h2>
        <p>
          This website is provided by {SITE_NAME} to share information about its services,
          projects, and insights. You may browse and use the site for lawful, personal, and
          business informational purposes.
        </p>

        <h2>Intellectual property</h2>
        <p>
          The design, code, content, and visual systems on this website are the property of
          {" "}{SITE_NAME}, except where otherwise noted, and may not be copied or reused
          without permission.
        </p>

        <h2>No guarantee of outcomes on this website</h2>
        <p>
          Information published on this website — including service descriptions and project
          summaries — is provided for general informational purposes. It does not constitute
          a binding proposal, quote, or guarantee of results. Project scope, timelines, and
          deliverables are defined separately in a written agreement between {SITE_NAME} and
          the client.
        </p>

        <h2>Third-party links</h2>
        <p>
          This website may reference external tools or services. {SITE_NAME} is not
          responsible for the content or practices of third-party websites.
        </p>

        <h2>Limitation of liability</h2>
        <p>
          {SITE_NAME} is not liable for any indirect, incidental, or consequential damages
          arising from use of this website, to the fullest extent permitted by law.
        </p>

        <h2>Changes to these terms</h2>
        <p>
          These terms may be updated periodically. Continued use of the website after changes
          are published constitutes acceptance of the updated terms.
        </p>

        <h2>Contact</h2>
        <p>
          Questions about these terms can be directed to{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </section>
    </>
  );
}
