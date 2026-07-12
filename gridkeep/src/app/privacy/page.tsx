import type { Metadata } from "next";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: `How ${SITE.name} collects, uses, and protects information submitted through this website.`,
  alternates: { canonical: "/privacy" },
  openGraph: { url: "/privacy", title: `Privacy Policy — ${SITE.name}` },
};

export default function PrivacyPage() {
  return (
    <>
      <JsonLd data={webPageSchema({ name: "Privacy Policy", description: metadata.description as string, path: "/privacy" })} />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Privacy Policy", path: "/privacy" }]} />

      <article className="bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-3xl">
          <h1 className="font-display text-4xl font-bold uppercase leading-tight sm:text-5xl">Privacy Policy</h1>
          <p className="mt-4 font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey-dim">Last updated: 12 July 2026</p>

          <div className="mt-10 space-y-8 text-sm leading-relaxed text-gk-grey">
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">1. Information We Collect</h2>
              <p>
                When you submit the project intake form on this website, GRIDKEEP collects the
                information you provide: name, work email, company, phone number, service of
                interest, budget range, project description, and preferred contact method. We do
                not collect this information through any other means on this site.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">2. How We Use Information</h2>
              <p>
                Information submitted through the contact form is used solely to respond to your
                inquiry and, if a project proceeds, to deliver the engagement. We do not sell or
                rent your information to third parties.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">3. Data Retention</h2>
              <p>
                Contact submissions are retained only for as long as necessary to respond to your
                inquiry or fulfil a project engagement, after which they are deleted upon request.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">4. Cookies &amp; Analytics</h2>
              <p>
                This website does not use third-party advertising cookies. Any analytics used are
                limited to aggregate, non-identifying usage data to improve site performance.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">5. Your Rights</h2>
              <p>
                You may request access to, correction of, or deletion of any information you have
                submitted by contacting {SITE.email}.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">6. Contact</h2>
              <p>
                Questions about this policy can be directed to {SITE.email}.
              </p>
            </section>
          </div>
        </div>
      </article>
    </>
  );
}
