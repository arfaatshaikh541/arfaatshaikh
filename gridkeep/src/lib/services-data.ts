export type ServiceSlug =
  | "ai-agents"
  | "automation"
  | "software-saas"
  | "cybersecurity"
  | "cloud-devops"
  | "business-systems"
  | "web-experiences";

export type ServiceDefinition = {
  slug: ServiceSlug;
  index: string;
  name: string;
  shortName: string;
  prototypeName: string;
  tagline: string;
  description: string;
  heroDescription: string;
  problems: string[];
  architecture: { label: string; detail: string }[];
  process: { step: string; detail: string }[];
  capabilities: string[];
  useCases: string[];
  faqs: { question: string; answer: string }[];
};

export const SERVICES: ServiceDefinition[] = [
  {
    slug: "ai-agents",
    index: "01",
    name: "AI & AI Agents",
    shortName: "AI Systems",
    prototypeName: "AI Inference Node",
    tagline: "Inference hardware logic, applied to your workflows.",
    description:
      "GRIDKEEP designs applied AI systems and autonomous agents that plug into real business processes — not demos.",
    heroDescription:
      "A modular compute node built to process, route, and act on data in real time. Input ports receive data, compute modules activate in sequence, and orange status pulses trace the path from ingestion to decision.",
    problems: [
      "Manual decision-making processes that don't scale with growth",
      "Fragmented data with no system that can reason over it",
      "AI pilots that never leave the demo stage",
    ],
    architecture: [
      { label: "Ingestion Layer", detail: "Structured and unstructured data enters through defined input ports." },
      { label: "Inference Core", detail: "Task-specific models process requests with monitored latency and cost." },
      { label: "Agent Orchestration", detail: "Multi-step agents plan, call tools, and escalate to humans when required." },
      { label: "Action Layer", detail: "Verified outputs are routed into your existing systems, not a new silo." },
    ],
    process: [
      { step: "Diagnose", detail: "We map the decision points worth automating and the ones that aren't." },
      { step: "Design", detail: "Model selection, guardrails, and evaluation criteria are defined before code." },
      { step: "Build", detail: "Agents and inference pipelines are built against your real data and systems." },
      { step: "Operate", detail: "Monitoring, cost controls, and human-in-the-loop review stay in place post-launch." },
    ],
    capabilities: [
      "Applied AI strategy and feasibility assessment",
      "Autonomous and semi-autonomous agent design",
      "Retrieval-augmented and fine-tuned inference pipelines",
      "Human-in-the-loop review and escalation systems",
      "Cost, latency, and accuracy monitoring",
    ],
    useCases: [
      "Customer engagement agents that route and resolve tickets",
      "Document and contract processing pipelines",
      "Internal knowledge agents connected to operational data",
    ],
    faqs: [
      {
        question: "Do you build on top of existing models or train new ones?",
        answer:
          "Almost always the former. We architect around proven foundation models with retrieval, tooling, and guardrails specific to your data — training from scratch is rarely the right tradeoff.",
      },
      {
        question: "How do you prevent AI agents from taking unsafe actions?",
        answer:
          "Every agent ships with defined action boundaries, confidence thresholds, and human escalation paths before it can write to a production system.",
      },
    ],
  },
  {
    slug: "automation",
    index: "02",
    name: "Business Automation",
    shortName: "Automation",
    prototypeName: "Automation Cell",
    tagline: "Precision handling for repetitive operational work.",
    description:
      "GRIDKEEP engineers automation cells that inspect, validate, route, and act on business processes with the same discipline as a factory line.",
    heroDescription:
      "A precision automation station: a robotic arm, vision-based scanning, and sorting rails that validate work as it arrives and route it to the correct outcome — accepted or rejected, logged either way.",
    problems: [
      "Manual, repetitive processes that consume operational headcount",
      "Inconsistent handling of exceptions and edge cases",
      "No audit trail for what was automated and why",
    ],
    architecture: [
      { label: "Intake", detail: "Work items — orders, records, tickets — enter through a defined queue." },
      { label: "Validation", detail: "Rules and vision-based checks confirm the item matches expected criteria." },
      { label: "Routing", detail: "Verified items continue automatically; exceptions are rejected to a review queue." },
      { label: "Audit Layer", detail: "Every decision is logged with the criteria that produced it." },
    ],
    process: [
      { step: "Map the process", detail: "We document the current manual workflow end to end." },
      { step: "Automate incrementally", detail: "High-confidence steps are automated first; edge cases stay human-reviewed." },
      { step: "Validate", detail: "Outputs are checked against the manual process before full cutover." },
      { step: "Scale", detail: "Once stable, the automation cell absorbs volume without added headcount." },
    ],
    capabilities: [
      "Workflow and process automation design",
      "Robotic process automation and system integration",
      "Exception handling and human review queues",
      "Audit logging and compliance-ready trails",
    ],
    useCases: [
      "Order and invoice processing pipelines",
      "Document intake and classification",
      "Operational quality control checkpoints",
    ],
    faqs: [
      {
        question: "What happens when the automation encounters something unexpected?",
        answer:
          "Every automation cell has a defined rejection path — unexpected items are routed to a review queue instead of silently failing or producing bad output.",
      },
    ],
  },
  {
    slug: "software-saas",
    index: "03",
    name: "Custom Software",
    shortName: "Software",
    prototypeName: "Software System Rack",
    tagline: "Architecture you can point at and explain.",
    description:
      "GRIDKEEP builds custom software and SaaS platforms as modular, physically-legible systems — every service has a defined job and a defined connection.",
    heroDescription:
      "A modular server rack: API gateway, authentication, application services, and database core slot into place one at a time, each connection illuminating as the architecture completes.",
    problems: [
      "Legacy software that can't be extended without breaking",
      "SaaS products stuck between MVP and production-grade",
      "No clear architecture that a new engineer can pick up",
    ],
    architecture: [
      { label: "API Gateway", detail: "A single, versioned entry point for every client." },
      { label: "Identity & Auth", detail: "Centralized authentication and authorization, not duplicated per service." },
      { label: "Application Services", detail: "Domain logic organized into services with clear ownership." },
      { label: "Data Layer", detail: "A database core with defined read/write paths and backup discipline." },
    ],
    process: [
      { step: "Scope", detail: "We define what the system must do — and explicitly what it won't." },
      { step: "Architect", detail: "Service boundaries, data model, and integration points are designed first." },
      { step: "Build", detail: "Incremental delivery against a working system, not a big-bang release." },
      { step: "Harden", detail: "Monitoring, logging, and backup layers are in place before launch." },
    ],
    capabilities: [
      "Custom SaaS and internal platform engineering",
      "API design and service architecture",
      "Legacy system modernization",
      "Database design and data migration",
    ],
    useCases: [
      "Internal operations platforms replacing spreadsheets",
      "Multi-tenant SaaS products",
      "API layers connecting legacy systems to modern clients",
    ],
    faqs: [
      {
        question: "Do you work with an existing codebase or only greenfield builds?",
        answer:
          "Both. Most engagements involve extending or re-architecting an existing system rather than starting from zero.",
      },
    ],
  },
  {
    slug: "cybersecurity",
    index: "04",
    name: "Cybersecurity",
    shortName: "Cybersecurity",
    prototypeName: "Cybersecurity Vault",
    tagline: "Detection, isolation, and protection — engineered, not assumed.",
    description:
      "GRIDKEEP designs security systems as armored, testable appliances: identity checks, intrusion detection, and locked-down data storage.",
    heroDescription:
      "A layered security vault: a segmented door, biometric scanner, and hardware security module. Unauthorized input is detected, blocked, and the vault locks — while protected data stays inside an isolated chamber.",
    problems: [
      "Security treated as a checklist instead of an engineered system",
      "No tested response when an intrusion attempt actually occurs",
      "Sensitive data with no clear access boundary",
    ],
    architecture: [
      { label: "Perimeter", detail: "Authentication and access gates in front of every protected resource." },
      { label: "Detection", detail: "Intrusion sensors and anomaly checks run continuously, not on a schedule." },
      { label: "Isolation", detail: "Suspicious activity is contained before it reaches protected data." },
      { label: "Secure Storage", detail: "Encrypted, access-logged storage for the data that matters most." },
    ],
    process: [
      { step: "Assess", detail: "We test what's actually exposed, not what's assumed to be secure." },
      { step: "Harden", detail: "Access controls, encryption, and monitoring are implemented systematically." },
      { step: "Test", detail: "Controlled intrusion testing validates the defenses before they're relied on." },
      { step: "Monitor", detail: "Ongoing detection keeps the system accountable after launch." },
    ],
    capabilities: [
      "Security architecture and access control design",
      "Intrusion detection and monitoring systems",
      "Encrypted data storage and key management",
      "Security testing and hardening",
    ],
    useCases: [
      "Access control for sensitive business systems",
      "Encrypted document and data vaults",
      "Security monitoring for customer-facing platforms",
    ],
    faqs: [
      {
        question: "Do you perform penetration testing?",
        answer:
          "Yes, as part of a hardening engagement — testing is used to validate defenses we've built, not sold as a standalone checkbox exercise.",
      },
    ],
  },
  {
    slug: "cloud-devops",
    index: "05",
    name: "Cloud & DevOps",
    shortName: "Cloud & DevOps",
    prototypeName: "Cloud Deployment Array",
    tagline: "Infrastructure that stays online when a node doesn't.",
    description:
      "GRIDKEEP builds cloud infrastructure and deployment pipelines as physical, observable systems — nodes, load balancing, and failover you can reason about.",
    heroDescription:
      "A modular server array: build packages deploy across compute nodes, traffic balances dynamically, and a failed node is isolated automatically while the rest of the system stays online.",
    problems: [
      "Manual deployments that break under real traffic",
      "No visibility into what's actually running in production",
      "Infrastructure cost that scales faster than the business",
    ],
    architecture: [
      { label: "Build Pipeline", detail: "Code is packaged and tested consistently, every time." },
      { label: "Deployment", detail: "Containers distribute across nodes with defined rollout strategy." },
      { label: "Load Balancing", detail: "Traffic is routed dynamically based on node health." },
      { label: "Observability", detail: "Metrics and logs are visible before, during, and after every deploy." },
    ],
    process: [
      { step: "Baseline", detail: "We assess current infrastructure cost, reliability, and deployment process." },
      { step: "Automate", detail: "CI/CD pipelines replace manual deployment steps." },
      { step: "Harden", detail: "Load balancing, autoscaling, and failover are configured and tested." },
      { step: "Operate", detail: "Observability dashboards keep the system accountable after go-live." },
    ],
    capabilities: [
      "Cloud infrastructure design and cost optimization",
      "CI/CD pipeline engineering",
      "Container orchestration and deployment automation",
      "Observability, alerting, and incident response",
    ],
    useCases: [
      "Migrating legacy infrastructure to modern cloud platforms",
      "Zero-downtime deployment pipelines",
      "Multi-region failover architecture",
    ],
    faqs: [
      {
        question: "Which cloud providers do you work with?",
        answer:
          "We architect for the major providers based on your existing footprint and cost profile rather than defaulting to one vendor.",
      },
    ],
  },
  {
    slug: "business-systems",
    index: "06",
    name: "Business Systems",
    shortName: "Business Systems",
    prototypeName: "Business Systems Hub",
    tagline: "One operating picture instead of six disconnected tools.",
    description:
      "GRIDKEEP integrates CRM, ERP, finance, and operations tooling into a single synchronized system of record.",
    heroDescription:
      "A central synchronization processor with CRM, ERP, finance, and operations modules connected by physical data pathways — duplicate records collapse and one consistent system state emerges.",
    problems: [
      "Customer, finance, and operations data that disagree with each other",
      "Manual reconciliation between disconnected tools",
      "No single source of truth for reporting decisions",
    ],
    architecture: [
      { label: "Integration Bridges", detail: "Each system connects through a defined, monitored data pathway." },
      { label: "Sync Processor", detail: "A central layer reconciles records and resolves conflicts by rule." },
      { label: "Analytics", detail: "Reporting reads from the synchronized state, not individual tools." },
      { label: "Access Control", detail: "Each module keeps its own permission boundary inside the shared system." },
    ],
    process: [
      { step: "Inventory", detail: "We map every system currently holding a piece of the truth." },
      { step: "Integrate", detail: "Systems are connected through defined, monitored integration points." },
      { step: "Reconcile", detail: "Conflicting records are resolved by rule, not manual cleanup." },
      { step: "Report", detail: "One dashboard reflects the synchronized state of the business." },
    ],
    capabilities: [
      "CRM, ERP, and finance system integration",
      "Data synchronization and conflict resolution",
      "Operational reporting and dashboards",
      "Legacy system consolidation",
    ],
    useCases: [
      "Unifying sales, finance, and support into one record",
      "Replacing spreadsheet-based operations with a system of record",
      "Consolidating tooling after a merger or rapid growth",
    ],
    faqs: [
      {
        question: "Do we need to replace our existing CRM or ERP?",
        answer:
          "Usually not. Integration is almost always cheaper and less disruptive than replacement — we connect what you have first.",
      },
    ],
  },
  {
    slug: "web-experiences",
    index: "07",
    name: "Web Experiences",
    shortName: "Web Experiences",
    prototypeName: "Web Experience Testing Rig",
    tagline: "Immersive interfaces, tested like hardware.",
    description:
      "GRIDKEEP designs and engineers immersive web experiences — real-time 3D, motion systems, and responsive interfaces built for performance.",
    heroDescription:
      "An interface testing rig: display panels are tested and physically rearranged across desktop, tablet, and mobile layouts, with a camera tracking module verifying every interaction path.",
    problems: [
      "Marketing sites that don't reflect engineering quality",
      "3D or motion-heavy sites that crash on mobile devices",
      "No performance discipline behind an ambitious design",
    ],
    architecture: [
      { label: "Render Layer", detail: "Real-time 3D and motion built on WebGL with a hard performance budget." },
      { label: "Layout Engine", detail: "Interfaces are tested and adapted across desktop, tablet, and mobile." },
      { label: "Interaction Layer", detail: "Input and scroll behavior is calibrated device by device." },
      { label: "Delivery", detail: "Assets are compressed and lazy-loaded to protect load time." },
    ],
    process: [
      { step: "Direct", detail: "Visual direction and technical constraints are defined together, not separately." },
      { step: "Prototype", detail: "Core 3D and motion systems are validated for performance before full build." },
      { step: "Build", detail: "The full experience is built with fallbacks for constrained devices." },
      { step: "Tune", detail: "Performance is profiled and tuned across real devices before launch." },
    ],
    capabilities: [
      "Real-time 3D and WebGL engineering",
      "Motion design and scroll-driven interaction",
      "Performance budgeting across devices",
      "Design systems for immersive interfaces",
    ],
    useCases: [
      "Flagship product and brand experiences",
      "Interactive data and system visualizations",
      "High-performance marketing sites with real 3D",
    ],
    faqs: [
      {
        question: "What happens on devices that can't run WebGL?",
        answer:
          "Every experience ships with a static, accessible fallback — the site never breaks or blanks on unsupported devices.",
      },
    ],
  },
];

export function getServiceBySlug(slug: string): ServiceDefinition | undefined {
  return SERVICES.find((s) => s.slug === slug);
}
