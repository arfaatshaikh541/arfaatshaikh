import type { Metadata } from "next";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import ContactPortalSection from "@/components/sections/ContactPortalSection";
import { contactPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: `Start a project with ${SITE.name}. Direct: ${SITE.email} — ${SITE.location}.`,
  alternates: { canonical: "/contact" },
  openGraph: { url: "/contact", title: `Contact — ${SITE.name}` },
};

export default function ContactPage() {
  return (
    <>
      <JsonLd data={contactPageSchema()} />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Contact", path: "/contact" }]} />
      <ContactPortalSection />
    </>
  );
}
