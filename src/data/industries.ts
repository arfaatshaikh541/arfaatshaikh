import type { Industry } from "@/types";

export const industries: Industry[] = [
  {
    slug: "professional-services",
    name: "Professional Services",
    description:
      "Auditing, accounting, advisory, legal, and consulting firms coordinating client work across teams that need shared, reliable systems rather than spreadsheets and email threads.",
    relevantServices: ["software-saas", "business-systems", "cybersecurity"],
  },
  {
    slug: "retail-hospitality",
    name: "Retail & Hospitality",
    description:
      "Salons, clinics, gyms, restaurants, and service businesses managing bookings, customer engagement, and operations across multiple locations or channels.",
    relevantServices: ["ai-agents", "web-experiences", "automation"],
  },
  {
    slug: "real-estate-construction",
    name: "Real Estate & Construction",
    description:
      "Developers, agencies, and contractors coordinating projects, documentation, and client communication across long, multi-stage timelines.",
    relevantServices: ["business-systems", "automation", "software-saas"],
  },
  {
    slug: "financial-services",
    name: "Financial Services",
    description:
      "Firms handling sensitive financial data and regulatory obligations that require security-first architecture and dependable reporting infrastructure.",
    relevantServices: ["cybersecurity", "business-systems", "cloud-devops"],
  },
  {
    slug: "healthcare-wellness",
    name: "Healthcare & Wellness",
    description:
      "Clinics and wellness providers managing patient scheduling, records, and communication with strict privacy and reliability requirements.",
    relevantServices: ["software-saas", "cybersecurity", "ai-agents"],
  },
  {
    slug: "logistics-trade",
    name: "Logistics & Trade",
    description:
      "Trading, freight, and logistics operators moving data across suppliers, customs, and delivery partners where automation removes manual bottlenecks.",
    relevantServices: ["automation", "cloud-devops", "business-systems"],
  },
];

export function getIndustryBySlug(slug: string) {
  return industries.find((industry) => industry.slug === slug);
}
