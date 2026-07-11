import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import PageIntro from "@/components/sections/PageIntro";
import ServiceCard from "@/components/ui/ServiceCard";
import ContactPortal from "@/components/sections/ContactPortal";
import { services } from "@/data/services";

export const metadata = buildMetadata({
  title: "Services",
  description:
    "GRIDKEEP's technology systems: AI and AI agents, business automation, custom software and SaaS, cybersecurity, cloud and DevOps, business systems, and web experiences.",
  path: "/services",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "Services", path: "/services" },
];

export default function ServicesPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <Breadcrumbs items={crumbs} />
      <PageIntro
        eyebrow="Full Capability Index"
        title={
          <>
            SYSTEMS FOR EVERY LAYER <span className="text-orange-primary">OF THE BUSINESS.</span>
          </>
        }
        description="From applied AI to cloud infrastructure, GRIDKEEP engineers connected technology systems — not isolated tools. Explore each capability below."
        model="grid"
      />

      <section className="border-b border-line bg-black-near py-16 md:py-24" aria-label="All services">
        <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-4 px-6 sm:grid-cols-2 md:px-10 lg:grid-cols-3">
          {services.map((service) => (
            <ServiceCard key={service.slug} service={service} />
          ))}
        </div>
      </section>

      <ContactPortal />
    </>
  );
}
