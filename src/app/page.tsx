import { HeroSection } from "@/components/sections/HeroSection";
import { BrandStatement } from "@/components/sections/BrandStatement";
import { ServiceChapter } from "@/components/sections/ServiceChapter";
import { ProjectsSection } from "@/components/sections/ProjectsSection";
import { FounderSection } from "@/components/sections/FounderSection";
import { EcosystemSection } from "@/components/sections/EcosystemSection";
import { ContactPortalSection } from "@/components/sections/ContactPortalSection";
import { JsonLd } from "@/components/seo/JsonLd";
import { webPageSchema } from "@/lib/schema";
import { services } from "@/data/services";

export default function HomePage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "GRIDKEEP — We build the systems behind the business.",
          description:
            "GRIDKEEP designs and engineers AI, automation, custom software, cybersecurity, cloud infrastructure, and immersive digital experiences.",
          path: "/",
        })}
      />
      <HeroSection />
      <BrandStatement />
      {services.map((service, index) => (
        <ServiceChapter key={service.slug} service={service} index={index} />
      ))}
      <ProjectsSection />
      <FounderSection />
      <EcosystemSection />
      <ContactPortalSection />
    </>
  );
}
