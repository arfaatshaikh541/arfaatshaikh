import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import { CONTACT_EMAIL, LOCATION, SITE_NAME } from "@/lib/constants";

export const metadata = buildMetadata({
  title: "Privacy Policy",
  description: `How ${SITE_NAME} collects, uses, and protects information submitted through this website.`,
  path: "/privacy",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "Privacy Policy", path: "/privacy" },
];

export default function PrivacyPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <Breadcrumbs items={crumbs} />
      <article className="border-b border-line bg-black py-16 md:py-24">
        <div className="mx-auto max-w-3xl px-6 md:px-10">
          <p className="gk-eyebrow mb-5">Legal</p>
          <h1 className="gk-heading text-4xl text-warmwhite sm:text-5xl">Privacy Policy</h1>
          <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.1em] text-muted">Last updated: July 2026</p>

          <div className="mt-10 flex flex-col gap-8 text-sm leading-relaxed text-warmwhite/85 md:text-base">
            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">1. Overview</h2>
              <p className="mt-3">
                {SITE_NAME} (&ldquo;GRIDKEEP,&rdquo; &ldquo;we,&rdquo; &ldquo;us&rdquo;) operates this website. This
                policy explains what information we collect through the site, how we use it, and the choices you
                have. {SITE_NAME} is based in {LOCATION}.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">2. Information We Collect</h2>
              <p className="mt-3">
                When you submit the contact form, we collect the information you provide directly: your name, work
                email, company, selected service, and project description. We do not require you to create an
                account to use this site.
              </p>
              <p className="mt-3">
                Like most websites, our hosting and analytics infrastructure may automatically log standard technical
                information such as IP address, browser type, device type, and pages visited, for security and
                performance purposes.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">3. How We Use Information</h2>
              <p className="mt-3">
                We use the information you submit to respond to your inquiry, evaluate a potential project, and
                communicate with you about that project. We do not sell personal information to third parties.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">4. Data Retention</h2>
              <p className="mt-3">
                We retain contact form submissions for as long as reasonably necessary to respond to your inquiry and
                maintain business records, after which they are deleted or anonymized.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">5. Your Rights</h2>
              <p className="mt-3">
                You may request access to, correction of, or deletion of personal information you have submitted to
                us by contacting {CONTACT_EMAIL}.
              </p>
            </section>

            <section>
              <h2 className="font-display text-lg uppercase tracking-wide text-warmwhite">6. Contact</h2>
              <p className="mt-3">
                Questions about this policy can be directed to{" "}
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
