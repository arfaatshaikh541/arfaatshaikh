import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { itemListSchema } from "@/lib/schema";
import { services } from "@/data/services";
import { projects } from "@/data/projects";
import { JsonLd } from "@/components/seo/JsonLd";
import { Hero } from "@/components/sections/Hero";
import { AboutSnapshot } from "@/components/sections/AboutSnapshot";
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
      <JsonLd
        data={[
          itemListSchema(
            "Services",
            services.map((service) => ({
              name: service.name,
              path: `/services/${service.slug}`,
              description: service.tagline,
            }))
          ),
          itemListSchema(
            "Featured Projects",
            projects.map((project) => ({
              name: project.title,
              path: `/projects/${project.slug}`,
              description: project.summary,
            }))
          ),
        ]}
      />
      <Hero />
      <AboutSnapshot />
      <SelectedProjects />
      <ServiceOverview />
      <FounderSection />
      <GridkeepSection />
      <CapabilitiesSection />
      <PhilosophySection />
      <TechStackSection />
      <ContactCta />
    </>
  );
}
