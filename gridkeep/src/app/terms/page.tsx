import type { Metadata } from "next";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: `Terms governing the use of the ${SITE.name} website and engagement with ${SITE.name} for project work.`,
  alternates: { canonical: "/terms" },
  openGraph: { url: "/terms", title: `Terms of Service — ${SITE.name}` },
};

export default function TermsPage() {
  return (
    <>
      <JsonLd data={webPageSchema({ name: "Terms of Service", description: metadata.description as string, path: "/terms" })} />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Terms of Service", path: "/terms" }]} />

      <article className="bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-3xl">
          <h1 className="font-display text-4xl font-bold uppercase leading-tight sm:text-5xl">Terms of Service</h1>
          <p className="mt-4 font-mono-tech text-xs uppercase tracking-[0.12em] text-gk-grey-dim">Last updated: 12 July 2026</p>

          <div className="mt-10 space-y-8 text-sm leading-relaxed text-gk-grey">
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">1. Use of This Website</h2>
              <p>
                This website is provided by GRIDKEEP to describe its services and provide a
                channel for project inquiries. Content on this site is informational and does not
                constitute a binding offer or contract.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">2. Project Engagements</h2>
              <p>
                Any project engagement with GRIDKEEP is governed by a separate, signed statement
                of work agreed directly between GRIDKEEP and the client, not by this website.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">3. Intellectual Property</h2>
              <p>
                All content, design, and code on this website — including its 3D prototypes and
                visual systems — are the property of GRIDKEEP unless otherwise stated.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">4. No Warranty</h2>
              <p>
                This website is provided &quot;as is&quot; without warranties of any kind. GRIDKEEP
                does not guarantee uninterrupted or error-free operation of this site.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">5. Governing Law</h2>
              <p>
                These terms are governed by the laws of the United Arab Emirates.
              </p>
            </section>
            <section>
              <h2 className="font-display mb-2 text-xl font-semibold text-gk-white">6. Contact</h2>
              <p>Questions about these terms can be directed to {SITE.email}.</p>
            </section>
          </div>
        </div>
      </article>
    </>
  );
}
