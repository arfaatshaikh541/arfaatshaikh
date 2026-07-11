import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { ChapterScroll } from "@/components/sections/ChapterScroll";
import { IntroStatement } from "@/components/sections/IntroStatement";
import { ServiceOverview } from "@/components/sections/ServiceOverview";
import { SelectedProjects } from "@/components/sections/SelectedProjects";
import { FounderSection } from "@/components/sections/FounderSection";
import { GridkeepSection } from "@/components/sections/GridkeepSection";
import { CapabilitiesSection } from "@/components/sections/CapabilitiesSection";
import { PhilosophySection } from "@/components/sections/PhilosophySection";
import { TechStackSection } from "@/components/sections/TechStackSection";
import { ContactCta } from "@/components/sections/ContactCta";

export const metadata: Metadata = buildMetadata({
  title: "Arfaat Shaikh — Creative Engineer & Founder of GRIDKEEP",
  description:
    "Arfaat Shaikh is a creative engineer in the United Arab Emirates and founder of GRIDKEEP, building AI agents, automation, custom software, cybersecurity, cloud infrastructure, and immersive web experiences.",
  path: "/",
});

export default function HomePage() {
  return (
    <>
      <ChapterScroll />
      <IntroStatement />
      <ServiceOverview />
      <SelectedProjects />
      <FounderSection />
      <GridkeepSection />
      <CapabilitiesSection />
      <PhilosophySection />
      <TechStackSection />
      <ContactCta />
    </>
  );
}
