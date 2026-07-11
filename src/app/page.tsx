import { buildMetadata } from "@/lib/seo";
import Hero from "@/components/sections/Hero";
import ServicesOverview from "@/components/sections/ServicesOverview";
import PrototypeChapters from "@/components/sections/PrototypeChapters";
import Projects from "@/components/sections/Projects";
import Founder from "@/components/sections/Founder";
import Ecosystem from "@/components/sections/Ecosystem";
import ContactPortal from "@/components/sections/ContactPortal";
import ScrollReveal from "@/components/ui/ScrollReveal";

export const metadata = buildMetadata({
  title: "Systems Behind The Business",
  description:
    "GRIDKEEP is a founder-led technology systems company engineering AI, automation, software, cybersecurity, cloud infrastructure, and immersive digital experiences.",
  path: "/",
});

export default function HomePage() {
  return (
    <>
      <Hero />
      <ScrollReveal>
        <ServicesOverview />
      </ScrollReveal>
      <ScrollReveal>
        <PrototypeChapters />
      </ScrollReveal>
      <ScrollReveal>
        <Projects />
      </ScrollReveal>
      <ScrollReveal>
        <Founder />
      </ScrollReveal>
      <ScrollReveal>
        <Ecosystem />
      </ScrollReveal>
      <ScrollReveal>
        <ContactPortal />
      </ScrollReveal>
    </>
  );
}
