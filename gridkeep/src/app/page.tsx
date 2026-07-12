import type { Metadata } from "next";
import Bootloader from "@/components/sections/Bootloader";
import HeroSection from "@/components/sections/HeroSection";
import ServicesGrid from "@/components/sections/ServicesGrid";
import ChaptersSection from "@/components/sections/ChaptersSection";
import CloudSection from "@/components/sections/CloudSection";
import WebExperienceSection from "@/components/sections/WebExperienceSection";
import ProjectsSection from "@/components/sections/ProjectsSection";
import FounderSection from "@/components/sections/FounderSection";
import EcosystemSection from "@/components/sections/EcosystemSection";
import ContactPortalSection from "@/components/sections/ContactPortalSection";
import JsonLd from "@/components/ui/JsonLd";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: `${SITE.name} — Founder-Led Technology Systems`,
  description: SITE.description,
  alternates: { canonical: "/" },
  openGraph: {
    url: "/",
    title: `${SITE.name} — Founder-Led Technology Systems`,
    description: SITE.description,
  },
};

export default function Home() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: `${SITE.name} — Founder-Led Technology Systems`,
          description: SITE.description,
          path: "/",
        })}
      />
      <Bootloader />
      <HeroSection />
      <ServicesGrid />
      <ChaptersSection />
      <CloudSection />
      <WebExperienceSection />
      <ProjectsSection />
      <FounderSection />
      <EcosystemSection />
      <ContactPortalSection />
    </>
  );
}
