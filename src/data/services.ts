import type { ServiceSummary } from "@/types";

export const services: ServiceSummary[] = [
  {
    slug: "ai-agents",
    index: "01",
    title: "AI & AI Agents",
    shortTitle: "AI & Agents",
    description: "Intelligent systems that think, learn and adapt.",
    longDescription:
      "GRIDKEEP designs and deploys applied AI systems and autonomous agents that plug directly into your operations — from decision support to task execution — engineered around real business workflows rather than generic chat interfaces.",
    capabilities: [
      "Custom AI agent design and orchestration",
      "LLM integration and prompt architecture",
      "Applied machine learning pipelines",
      "AI-driven decision and analysis systems",
    ],
    model: "cluster",
  },
  {
    slug: "automation",
    index: "02",
    title: "Business Automation",
    shortTitle: "Automation",
    description: "Automate processes and eliminate operational friction.",
    longDescription:
      "We map, redesign, and automate the operational processes that quietly drain time and margin — connecting tools, removing manual handoffs, and building automation engines that keep running without supervision.",
    capabilities: [
      "Workflow and process automation",
      "Systems integration and orchestration",
      "Robotic and rules-based task automation",
      "Operational monitoring and alerting",
    ],
    model: "automation",
  },
  {
    slug: "software-saas",
    index: "03",
    title: "Custom Software",
    shortTitle: "Custom Software",
    description: "Scalable software and SaaS platforms built for growth.",
    longDescription:
      "From internal tools to full SaaS products, GRIDKEEP engineers custom software with production-grade architecture — built to scale, maintainable long after launch, and designed around the way your business actually works.",
    capabilities: [
      "Full-stack product engineering",
      "SaaS architecture and multi-tenant systems",
      "API-first backend design",
      "Design systems and product UI",
    ],
    model: "architecture",
  },
  {
    slug: "cybersecurity",
    index: "04",
    title: "Cybersecurity",
    shortTitle: "Cybersecurity",
    description: "Protect systems, data and digital infrastructure.",
    longDescription:
      "GRIDKEEP builds security into systems from the foundation up — hardening infrastructure, auditing exposure, and engineering defensive layers so business-critical systems stay resilient under real-world conditions.",
    capabilities: [
      "Security architecture and hardening",
      "Infrastructure and application audits",
      "Access control and identity systems",
      "Monitoring and incident response readiness",
    ],
    model: "vault",
  },
  {
    slug: "cloud-devops",
    index: "05",
    title: "Cloud & DevOps",
    shortTitle: "Cloud & DevOps",
    description: "Secure, scalable and high-performance infrastructure.",
    longDescription:
      "We architect and operate cloud infrastructure and delivery pipelines that stay stable under load — provisioning, deployment automation, and observability engineered for teams that need to move fast without breaking production.",
    capabilities: [
      "Cloud architecture and provisioning",
      "CI/CD pipeline design",
      "Infrastructure as code",
      "Performance monitoring and observability",
    ],
    model: "cloud",
  },
  {
    slug: "business-systems",
    index: "06",
    title: "Business Systems",
    shortTitle: "Business Systems",
    description: "CRM, ERP, APIs and data systems that work in perfect sync.",
    longDescription:
      "GRIDKEEP connects the systems that run your business — CRM, ERP, data platforms, and third-party APIs — into a single coherent operating layer, removing duplicate data entry and disconnected tooling.",
    capabilities: [
      "CRM and ERP implementation",
      "API integration and middleware",
      "Data dashboards and reporting systems",
      "Cross-platform system architecture",
    ],
    model: "grid",
  },
  {
    slug: "web-experiences",
    index: "07",
    title: "Web Experiences",
    shortTitle: "Web Experiences",
    description: "Immersive, technically engineered digital experiences.",
    longDescription:
      "We build immersive web experiences — 3D interfaces, motion-driven storytelling, and interactive product sites — engineered with the same rigor as production software, not template-built marketing pages.",
    capabilities: [
      "Three.js and WebGL development",
      "Motion design and scroll choreography",
      "Interactive product and brand sites",
      "Performance-first front-end engineering",
    ],
    model: "reactor",
  },
];
