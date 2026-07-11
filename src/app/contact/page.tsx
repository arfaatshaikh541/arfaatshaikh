import type { Metadata } from "next";
import { buildMetadata, siteConfig } from "@/lib/seo";
import { breadcrumbSchema, contactPageSchema } from "@/lib/schema";
import { JsonLd } from "@/components/seo/JsonLd";
import { PageHeader } from "@/components/ui/PageHeader";
import { ContactForm } from "@/components/forms/ContactForm";

export const metadata: Metadata = buildMetadata({
  title: "Contact",
  description:
    "Start a conversation about AI agents, automation, custom software, cybersecurity, cloud infrastructure, or an immersive web experience.",
  path: "/contact",
});

export default function ContactPage() {
  return (
    <>
      <JsonLd
        data={[
          contactPageSchema(),
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Contact", path: "/contact" },
          ]),
        ]}
      />

      <PageHeader
        eyebrow="Start a Project"
        title="Contact"
        description="Tell me about the problem, not just the tool you think you need. I read every enquiry personally and reply with an honest read on scope and fit."
        crumbs={[
          { name: "Home", href: "/" },
          { name: "Contact", href: "/contact" },
        ]}
      />

      <section className="container-edge grid gap-16 py-24 md:grid-cols-[2fr_1fr] md:py-32">
        <ContactForm />

        <aside className="space-y-10">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
              Direct
            </p>
            <a
              href={`mailto:${siteConfig.email}`}
              className="mt-3 block text-lg text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              {siteConfig.email}
            </a>
          </div>

          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
              Location
            </p>
            <p className="mt-3 text-lg text-[var(--color-off-white)]">United Arab Emirates</p>
          </div>

          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
              Studio
            </p>
            <a
              href={siteConfig.gridkeepUrl}
              className="mt-3 block text-lg text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              GRIDKEEP
            </a>
          </div>

          <div className="border-t border-[var(--color-line)] pt-8">
            <p className="text-sm leading-relaxed text-[var(--color-muted)]">
              Fields marked * are required. Submissions are validated and rate-limited, and
              your details are only ever used to respond to your enquiry — see the{" "}
              <a
                href="/privacy"
                className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
              >
                Privacy Policy
              </a>
              .
            </p>
          </div>
        </aside>
      </section>
    </>
  );
}
