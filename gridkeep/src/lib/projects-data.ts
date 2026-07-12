export type ProjectSlug = "rafana" | "ai-customer-engagement" | "gridkeep-digital-experience";

export type ProjectDefinition = {
  slug: ProjectSlug;
  name: string;
  status: string;
  summary: string;
  description: string;
  prototypeLabel: string;
  prototypeDescription: string;
  capabilities: string[];
  services: string[];
};

export const PROJECTS: ProjectDefinition[] = [
  {
    slug: "rafana",
    name: "RAFANA Digital Platform",
    status: "Client Platform",
    summary: "A professional financial operations platform built for UAE compliance requirements.",
    description:
      "RAFANA is a financial operations platform covering audit workflows, document processing, and compliance reporting for the UAE market. GRIDKEEP designed the system architecture and the operator-facing interface, presented as a financial operations terminal rather than a generic dashboard.",
    prototypeLabel: "Financial Operations Terminal",
    prototypeDescription:
      "A console-style interface built around audit dashboards, data panels, and a document processing module, styled to match the seriousness of financial and compliance work.",
    capabilities: [
      "Audit workflow dashboard",
      "Document processing module",
      "UAE compliance interface",
      "Role-based operator access",
    ],
    services: ["software-saas", "business-systems"],
  },
  {
    slug: "ai-customer-engagement",
    name: "AI Customer Engagement Platform",
    status: "In Development",
    summary: "A multi-channel communication and orchestration system for customer engagement.",
    description:
      "An AI-driven customer engagement platform combining a communication control console with multi-channel routing hardware logic — conversations are streamed, routed, and orchestrated across agents and tenants.",
    prototypeLabel: "Communication Control Console",
    prototypeDescription:
      "Multi-channel routing hardware with conversation streams, an agent orchestration module, and tenant-routing logic, represented as a physical control console rather than a chat widget mockup.",
    capabilities: [
      "Multi-channel message routing",
      "Agent orchestration module",
      "Tenant-based routing architecture",
      "Conversation stream monitoring",
    ],
    services: ["ai-agents", "automation"],
  },
  {
    slug: "gridkeep-digital-experience",
    name: "GRIDKEEP Digital Experience",
    status: "Internal Product",
    summary: "GRIDKEEP's own design system and WebGL interface engine.",
    description:
      "This website itself: a design system laboratory built around a WebGL interface engine, content system modules, and performance monitoring — engineered and maintained internally by GRIDKEEP.",
    prototypeLabel: "Design System Laboratory",
    prototypeDescription:
      "A WebGL interface engine paired with content system modules, performance monitoring, and deployment controls — the same infrastructure used to build every GRIDKEEP client project.",
    capabilities: [
      "WebGL interface engine",
      "Design system modules",
      "Performance monitoring",
      "Deployment controls",
    ],
    services: ["web-experiences", "software-saas"],
  },
];

export function getProjectBySlug(slug: string): ProjectDefinition | undefined {
  return PROJECTS.find((p) => p.slug === slug);
}
