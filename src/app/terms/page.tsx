import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import { CONTACT_EMAIL, LOCATION, SITE_NAME } from "@/lib/constants";

export const metadata = buildMetadata({
  title: "Terms of Service",
  description: `The terms governing use of the ${SITE_NAME} website.`,
  path: "/terms",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "Terms of Service", path: "/terms" },
];

export default function TermsPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <Breadcrumbs items={crumbs} />
      <article className="border-b border-line bg-black py-16 md:py-24">
        <div className="mx-auto max-w-3xl px-6 md:px-10">
          <p className="gk-eyebrow mb-5">Legal</p>
          <h1 className="gk-heading text-4xl text-warmwhite sm:text-5xl">Terms of Service</h1>
          <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.1em] text-muted">Last updated: July 2026</p>

          <div className="mt-10 flex flex-col gap-8 text-sm leading-relaxed text-warmwhite/85 md:text-base">
            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">1. Acceptance of Terms</h2>
              <p className="mt-3">
                By accessing this website, operated by {SITE_NAME} in {LOCATION}, you agree to these Terms of
                Service. If you do not agree, please do not use this site.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">2. Website Content</h2>
              <p className="mt-3">
                Content on this site — including text, graphics, and the interactive 3D experiences — is provided for
                informational purposes about {SITE_NAME}&rsquo;s services and is owned by or licensed to {SITE_NAME}
                unless otherwise noted. You may not reproduce or redistribute this content without permission.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">3. No Warranty</h2>
              <p className="mt-3">
                This website is provided &ldquo;as is.&rdquo; While we take reasonable care to keep it accurate and
                available, we make no warranty that the site will be uninterrupted or error-free.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">4. Project Engagements</h2>
              <p className="mt-3">
                Submitting the contact form or inquiring about a project does not, by itself, create a binding
                agreement. Any engagement for services is governed by a separate agreement entered into directly with
                {" "}{SITE_NAME}.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">5. Changes to These Terms</h2>
              <p className="mt-3">
                We may update these terms from time to time. Continued use of the site after changes are posted
                constitutes acceptance of the updated terms.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">6. Contact</h2>
              <p className="mt-3">
                Questions about these terms can be directed to{" "}
                <a href={`mailto:${CONTACT_EMAIL}`} className="text-orange-primary hover:text-orange-bright">
                  {CONTACT_EMAIL}
                </a>
                .
              </p>
            </section>
          </div>
        </div>
      </article>
    </>
  );
}
