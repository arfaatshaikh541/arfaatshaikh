import type { Metadata } from "next";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { ChapterScene } from "@/components/three/ChapterScene";
import { ContactForm } from "@/components/forms/ContactForm";
import { Reveal } from "@/components/ui/Reveal";
import { buildMetadata } from "@/lib/seo";
import { contactPageSchema } from "@/lib/schema";
import { CONTACT_EMAIL } from "@/lib/constants";

export const metadata: Metadata = buildMetadata({
  title: "Contact",
  description: "Start a project with GRIDKEEP. Tell us what you're building and where you want the business to be.",
  path: "/contact",
});

export default function ContactPage() {
  return (
    <>
      <JsonLd data={contactPageSchema()} />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Contact", path: "/contact" }]} />

      <div className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 opacity-60">
          <ChapterScene scene="portal" interactive className="h-full w-full" />
        </div>
        <PageHero
          eyebrow="Start a project"
          title="Tell us what you're building."
          description={`Reach out directly at ${CONTACT_EMAIL}, or use the form below. GRIDKEEP responds personally — no account managers, no handoffs.`}
        />
      </div>

      <section className="mx-auto max-w-3xl px-6 pb-32 md:px-10">
        <Reveal>
          <ContactForm />
        </Reveal>
      </section>
    </>
  );
}
