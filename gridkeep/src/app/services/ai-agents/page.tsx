import type { Metadata } from "next";
import ServiceDetailTemplate from "@/components/sections/ServiceDetailTemplate";
import { getServiceBySlug } from "@/lib/services-data";

const service = getServiceBySlug("ai-agents")!;

export const metadata: Metadata = {
  title: service.name,
  description: service.description,
  alternates: { canonical: `/services/${service.slug}` },
  openGraph: {
    url: `/services/${service.slug}`,
    title: service.name,
    description: service.description,
  },
};

export default function Page() {
  return <ServiceDetailTemplate service={service} />;
}
