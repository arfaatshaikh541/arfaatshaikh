import type { Service } from "@/types";

export const services: Service[] = [
  {
    slug: "ai-agents",
    name: "AI & AI Agents",
    shortName: "AI Agents",
    eyebrow: "ARTIFICIAL INTELLIGENCE",
    summary:
      "Autonomous agents and applied AI systems that act inside your business, not beside it.",
    description:
      "GRIDKEEP designs AI agents and applied AI systems that are wired directly into your operations — reading data, making decisions within defined boundaries, and executing real tasks across the tools you already run. This is not a chatbot bolted onto a website. It is decision infrastructure: agents that qualify leads, route support requests, monitor operations, and hand off to your team only when judgment is required.",
    capabilities: [
      "Custom AI agent design and orchestration",
      "LLM integration and prompt architecture",
      "Retrieval-augmented systems over your own data",
      "Agent-to-system automation (CRM, ERP, support, scheduling)",
      "Human-in-the-loop safeguards and escalation logic",
      "Evaluation, monitoring, and guardrails",
    ],
    scene: "neural",
    relatedIndustries: ["professional-services", "retail-hospitality", "real-estate-construction"],
    faqs: [
      {
        question: "Do AI agents replace my team?",
        answer:
          "No. GRIDKEEP builds agents to absorb repetitive, well-defined decisions and hand off ambiguous or high-stakes cases to your team, with a clear boundary between the two.",
      },
      {
        question: "What data do agents need access to?",
        answer:
          "Only what the task requires. Every agent is scoped to specific systems and permissions, defined during the architecture phase before any integration is built.",
      },
    ],
  },
  {
    slug: "automation",
    name: "Business Automation",
    shortName: "Automation",
    eyebrow: "OPERATIONS",
    summary:
      "Automation pipelines that move data through your business correctly, every time.",
    description:
      "GRIDKEEP engineers automation pipelines that replace manual handoffs between teams and tools. Every pipeline is built around five stages — trigger, process, validation, action, and reporting — so that data entering the system is checked before it is acted on, and every action is traceable after the fact.",
    capabilities: [
      "Workflow and process automation",
      "Cross-tool data pipelines",
      "Trigger-based operational logic",
      "Validation and error-handling layers",
      "Reporting and audit trails",
      "Legacy system integration",
    ],
    scene: "assembly",
    relatedIndustries: ["logistics-trade", "professional-services", "real-estate-construction"],
    faqs: [
      {
        question: "What happens when automated data is invalid?",
        answer:
          "Every pipeline includes a validation stage that rejects or flags invalid data before it reaches downstream systems, with visibility into why it failed.",
      },
    ],
  },
  {
    slug: "software-saas",
    name: "Custom Software & SaaS",
    shortName: "Software & SaaS",
    eyebrow: "PRODUCT ENGINEERING",
    summary:
      "Custom platforms and multi-tenant SaaS products built for how your business actually operates.",
    description:
      "GRIDKEEP builds custom software and SaaS platforms from architecture through deployment — API layers, database design, dashboards, and the service mesh connecting them. Every platform is modular by design, so new capabilities extend the system instead of requiring it to be rebuilt.",
    capabilities: [
      "Custom platform architecture and engineering",
      "Multi-tenant SaaS product design",
      "API design and integration layers",
      "Dashboard and internal tooling",
      "Database architecture and data modeling",
      "Ongoing platform maintenance",
    ],
    scene: "architecture",
    relatedIndustries: ["professional-services", "retail-hospitality", "healthcare-wellness"],
  },
  {
    slug: "cybersecurity",
    name: "Cybersecurity",
    shortName: "Cybersecurity",
    eyebrow: "PROTECTION",
    summary:
      "Security architecture that protects business-critical systems without slowing them down.",
    description:
      "GRIDKEEP designs cybersecurity architecture around access control, encryption, and monitoring — layered so that a single failure does not expose the whole system. Security is treated as infrastructure, built in at the architecture stage rather than added after launch.",
    capabilities: [
      "Security architecture and threat modeling",
      "Access control and identity management",
      "Data encryption at rest and in transit",
      "Monitoring and anomaly detection",
      "Incident response planning",
      "Security review of existing systems",
    ],
    scene: "vault",
    relatedIndustries: ["financial-services", "healthcare-wellness", "professional-services"],
  },
  {
    slug: "cloud-devops",
    name: "Cloud & DevOps",
    shortName: "Cloud & DevOps",
    eyebrow: "INFRASTRUCTURE",
    summary:
      "Cloud infrastructure and deployment pipelines built for resilience under real load.",
    description:
      "GRIDKEEP architects cloud infrastructure and DevOps pipelines that scale predictably — deployment automation, load balancing, observability, and infrastructure-as-code, so releases are routine instead of risky.",
    capabilities: [
      "Cloud infrastructure architecture",
      "CI/CD pipeline design",
      "Container orchestration and deployment automation",
      "Load balancing and scaling strategy",
      "Observability and monitoring systems",
      "Infrastructure-as-code",
    ],
    scene: "orbit",
    relatedIndustries: ["logistics-trade", "professional-services", "retail-hospitality"],
  },
  {
    slug: "business-systems",
    name: "Business Systems",
    shortName: "Business Systems",
    eyebrow: "CRM · ERP · DATA",
    summary:
      "CRM, ERP, and API integration that connects disconnected tools into one operating system.",
    description:
      "GRIDKEEP connects the systems businesses already depend on — CRM, ERP, finance, operations, and analytics — into a single synchronized network, removing duplicate data entry and giving every team a shared source of truth.",
    capabilities: [
      "CRM implementation and customization",
      "ERP integration and workflow design",
      "API integration between business systems",
      "Data synchronization and deduplication",
      "Analytics and reporting dashboards",
      "Legacy data migration",
    ],
    scene: "network",
    relatedIndustries: ["professional-services", "real-estate-construction", "financial-services"],
  },
  {
    slug: "web-experiences",
    name: "Immersive Web Experiences",
    shortName: "Web Experiences",
    eyebrow: "DIGITAL PRODUCT",
    summary:
      "High-performance, design-led websites and web applications engineered for brand impact.",
    description:
      "GRIDKEEP builds web experiences that hold up under real engineering scrutiny — performant, accessible, SEO-complete, and visually distinct, from marketing sites to interactive product interfaces.",
    capabilities: [
      "Design-led website engineering",
      "Interactive and immersive web interfaces",
      "Web application front-ends",
      "Performance and Core Web Vitals optimization",
      "Technical SEO implementation",
      "Design systems and component libraries",
    ],
    scene: "weblab",
    relatedIndustries: ["retail-hospitality", "professional-services", "real-estate-construction"],
  },
];

export function getServiceBySlug(slug: string) {
  return services.find((service) => service.slug === slug);
}
