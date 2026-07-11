import type { Service } from "@/types";

export const services: Service[] = [
  {
    slug: "ai-automation",
    name: "AI & Automation",
    shortName: "AI & Automation",
    tagline: "Intelligence that acts, not just answers.",
    heroDescription:
      "AI agents and automation systems designed to remove repetitive work from your business, connect your tools, and respond to customers and operations in real time.",
    overview: [
      "Most businesses do not need a chatbot bolted onto their website — they need a system that understands their operations, connects to the tools they already use, and takes real action without waiting on a human for every step.",
      "I design and build AI agents and automation pipelines that sit inside your actual workflow: answering customers, qualifying leads, processing documents, updating records, and triggering the next step in a process, so your team spends time on decisions instead of data entry.",
      "Every system is built to be observable and controllable. You can see what the agent decided, why, and step in whenever you need to — automation should reduce risk, not hide it.",
    ],
    problems: [
      "Customer enquiries pile up outside business hours with no consistent response.",
      "Staff spend hours a week on manual data entry between disconnected systems.",
      "Leads go cold because follow-up depends on someone remembering to do it.",
      "Repetitive internal processes (approvals, reporting, reminders) rely entirely on manual effort.",
      "Existing chatbots give generic answers and cannot take real action inside your systems.",
    ],
    capabilities: [
      {
        title: "Conversational AI agents",
        description:
          "Agents trained on your business context that handle customer conversations across web, WhatsApp, and email — with clear handoff to a human when needed.",
      },
      {
        title: "Workflow automation",
        description:
          "Event-driven pipelines that connect your CRM, calendar, inbox, and internal tools so information moves without manual re-entry.",
      },
      {
        title: "Document and data processing",
        description:
          "Automated extraction, validation, and routing of documents such as invoices, applications, and forms.",
      },
      {
        title: "Lead qualification and routing",
        description:
          "Agents that engage new leads immediately, ask the right qualifying questions, and route them to the correct team or pipeline stage.",
      },
      {
        title: "Internal operations agents",
        description:
          "Automations for reporting, reminders, approvals, and status updates that currently depend on someone remembering to do them manually.",
      },
      {
        title: "Human-in-the-loop controls",
        description:
          "Every automation includes visibility and override points, so your team stays in control of what the system decides.",
      },
    ],
    process: [
      {
        step: "01",
        title: "Map the workflow",
        description:
          "I study how work actually moves through your business today — the tools, the handoffs, and where time and information get lost.",
      },
      {
        step: "02",
        title: "Design the agent logic",
        description:
          "Define what the agent should decide autonomously, what needs human review, and how it should behave when it is unsure.",
      },
      {
        step: "03",
        title: "Build and connect",
        description:
          "Build the agent and connect it to your CRM, calendar, communication channels, and internal systems through APIs.",
      },
      {
        step: "04",
        title: "Test against real scenarios",
        description:
          "Run the system against real conversations and edge cases before it touches live customers or data.",
      },
      {
        step: "05",
        title: "Deploy with visibility",
        description:
          "Launch with logging and reporting in place so you can see exactly what the system is doing and adjust it over time.",
      },
    ],
    technologies: [
      "OpenAI & Anthropic APIs",
      "LangChain / custom agent orchestration",
      "Node.js & Python",
      "Vector databases",
      "Webhooks & REST/GraphQL APIs",
      "WhatsApp Business API",
      "Zapier / Make for lightweight integrations",
      "PostgreSQL",
    ],
    useCases: [
      "A salon or clinic that needs bookings and enquiries handled automatically outside working hours.",
      "A real estate business that wants new leads qualified and routed the moment they arrive.",
      "A service company that wants invoices and forms processed without manual data entry.",
      "An operations team drowning in repetitive status updates and internal approvals.",
    ],
    faqs: [
      {
        question: "Will an AI agent replace my team?",
        answer:
          "No. The goal is to remove repetitive, low-judgement work so your team can focus on conversations and decisions that actually need a person. Every agent I build includes a clear path to human handoff.",
      },
      {
        question: "What if the AI gives a wrong answer to a customer?",
        answer:
          "Agents are scoped to what they actually know about your business and are designed to escalate rather than guess when a question falls outside that scope. You also get visibility into every conversation.",
      },
      {
        question: "Can this connect to the tools we already use?",
        answer:
          "In most cases, yes. If a tool has an API — and most modern CRMs, calendars, and business platforms do — it can typically be connected into the automation.",
      },
      {
        question: "How long does an AI agent project take?",
        answer:
          "It depends on scope and how many systems need to be connected. A focused single-workflow agent takes considerably less time than a multi-department automation system. This is scoped honestly during discovery, not estimated generically.",
      },
    ],
    pillars: [
      {
        slug: "ai-agents",
        name: "AI Agents",
        tagline: "Agents that understand your business and act inside it.",
        summary:
          "Custom conversational and task-driven agents scoped to your business context, connected to your real systems.",
      },
      {
        slug: "business-automation",
        name: "Business Automation",
        tagline: "Remove the manual steps between your tools.",
        summary:
          "Event-driven automation pipelines that move information between your CRM, calendar, inbox, and internal systems.",
      },
    ],
    relatedSlugs: ["software-saas", "cloud-devops"],
  },
  {
    slug: "software-saas",
    name: "Custom Software & SaaS",
    shortName: "Software & SaaS",
    tagline: "Systems built around how your business actually works.",
    heroDescription:
      "Custom software, SaaS platforms, and business systems — CRM, ERP, dashboards, and API integrations — engineered for the way your business actually operates, not the way generic software assumes it does.",
    overview: [
      "Off-the-shelf software is built for the average business. Most businesses are not average — they have specific processes, exceptions, and relationships between departments that generic tools force into workarounds and spreadsheets.",
      "I build custom software and SaaS platforms that are shaped around your actual operations: multi-tenant systems for platforms serving many clients, internal tools that replace fragile spreadsheets, and integrations that connect CRM, ERP, and business systems into one coherent source of truth.",
      "The result is software that fits, scales with the business, and does not require you to change how you work to accommodate the tool.",
    ],
    problems: [
      "Generic software forces the business into workarounds and manual exceptions.",
      "Data lives in disconnected spreadsheets, CRMs, and inboxes with no single source of truth.",
      "Growing platforms need multi-tenant architecture that off-the-shelf tools cannot provide.",
      "Reporting requires manually pulling numbers from multiple systems.",
      "Existing systems cannot talk to each other without manual re-entry.",
    ],
    capabilities: [
      {
        title: "Custom software builds",
        description:
          "Purpose-built applications designed around your specific operations rather than generic assumptions.",
      },
      {
        title: "SaaS platform development",
        description:
          "Multi-tenant architecture, subscription logic, role-based access, and scalable data models for platforms serving multiple clients.",
      },
      {
        title: "CRM and ERP systems",
        description:
          "Systems for managing customers, pipelines, inventory, and operations, either built custom or integrated with existing platforms.",
      },
      {
        title: "API integrations",
        description:
          "Connecting your existing tools — payments, communication, accounting, and operational systems — into a single coherent flow.",
      },
      {
        title: "Data dashboards",
        description:
          "Operational and business dashboards that pull live data into one place instead of manual reporting.",
      },
      {
        title: "Business process engineering",
        description:
          "Mapping and rebuilding inefficient internal processes into structured, software-backed workflows.",
      },
    ],
    process: [
      {
        step: "01",
        title: "Understand the operation",
        description:
          "Study the business process the software needs to support, including the exceptions and edge cases generic tools tend to ignore.",
      },
      {
        step: "02",
        title: "Architect the system",
        description:
          "Design the data model, access control, and integration points before writing implementation code.",
      },
      {
        step: "03",
        title: "Build in stages",
        description:
          "Develop in reviewable increments so the direction can be corrected early rather than at the end.",
      },
      {
        step: "04",
        title: "Integrate and test",
        description:
          "Connect the system to existing tools and test against real operational scenarios, not just happy paths.",
      },
      {
        step: "05",
        title: "Deploy and support",
        description:
          "Launch with documentation and a clear plan for ongoing changes as the business evolves.",
      },
    ],
    technologies: [
      "TypeScript & Node.js",
      "React & Next.js",
      "Python",
      "PostgreSQL & MySQL",
      "Prisma",
      "REST & GraphQL APIs",
      "Stripe & payment integrations",
      "Docker",
    ],
    useCases: [
      "A multi-tenant platform serving salons, clinics, or service businesses with separate data per client.",
      "An internal tool replacing a fragile spreadsheet-based process.",
      "A CRM and accounting integration that removes manual double entry.",
      "A dashboard that gives leadership live visibility into operations instead of monthly reports.",
    ],
    faqs: [
      {
        question: "Why build custom instead of using off-the-shelf software?",
        answer:
          "Off-the-shelf tools are right for standard needs. Custom software makes sense when your process does not fit the standard mould, when you need multi-tenant scale, or when connecting existing tools would cost more in workarounds than a purpose-built system.",
      },
      {
        question: "Do you build multi-tenant SaaS platforms?",
        answer:
          "Yes. Multi-tenant architecture — separating and securing data per client while sharing a single codebase — is a core part of the SaaS platforms I build.",
      },
      {
        question: "Can you integrate with our existing CRM or accounting software?",
        answer:
          "In most cases, yes, provided the platform exposes an API. Integration scope is assessed during discovery against the specific tools you use.",
      },
      {
        question: "Who owns the code once the project is finished?",
        answer:
          "You do. Custom builds are delivered with full source code ownership unless otherwise agreed.",
      },
    ],
    pillars: [
      {
        slug: "custom-software",
        name: "Custom Software",
        tagline: "Applications built around your process, not a template.",
        summary:
          "Purpose-built software designed for the specific way your business operates.",
      },
      {
        slug: "saas-platforms",
        name: "SaaS Platforms",
        tagline: "Multi-tenant systems built to scale with your business.",
        summary:
          "Subscription-ready, multi-tenant platforms with role-based access and scalable data architecture.",
      },
      {
        slug: "crm-erp-systems",
        name: "CRM & ERP Systems",
        tagline: "One coherent view of customers and operations.",
        summary:
          "Custom or integrated systems for managing customers, pipelines, inventory, and operations.",
      },
      {
        slug: "api-integrations",
        name: "API Integrations",
        tagline: "Connect the tools you already rely on.",
        summary:
          "Integration work that removes manual re-entry between your existing business systems.",
      },
      {
        slug: "data-dashboards",
        name: "Data Dashboards",
        tagline: "Live operational visibility in one place.",
        summary:
          "Dashboards that surface live business and operational data without manual reporting.",
      },
    ],
    relatedSlugs: ["ai-automation", "cloud-devops"],
  },
  {
    slug: "cybersecurity",
    name: "Cybersecurity",
    shortName: "Cybersecurity",
    tagline: "Security built into the system, not added after.",
    heroDescription:
      "Practical cybersecurity for growing businesses — secure architecture, access control, and hardening for the software, infrastructure, and automation systems you rely on.",
    overview: [
      "Security is treated as an afterthought far too often — added once something goes wrong instead of being designed in from the start. That approach is expensive and risky.",
      "I build security into the software and infrastructure from the beginning: proper authentication and access control, secure API design, hardened cloud configuration, and sane data handling. For existing systems, I assess what is exposed and fix it in order of actual risk.",
      "This is practical, business-focused security — protecting customer data, business systems, and uptime — not a compliance checklist for its own sake.",
    ],
    problems: [
      "Customer and business data is exposed through weak access control or misconfigured systems.",
      "APIs and integrations are built without proper authentication or rate limiting.",
      "Cloud infrastructure is configured with excessive public access.",
      "There is no clear picture of what systems and data are actually exposed.",
      "Security is treated as a one-time task instead of an ongoing practice.",
    ],
    capabilities: [
      {
        title: "Secure architecture design",
        description:
          "Authentication, authorization, and data handling designed correctly from the first line of code.",
      },
      {
        title: "Application security review",
        description:
          "Assessment of existing software and APIs against common vulnerability classes (OWASP Top 10) with practical remediation.",
      },
      {
        title: "Infrastructure hardening",
        description:
          "Locking down cloud infrastructure, network access, and permissions to reduce the attack surface.",
      },
      {
        title: "Access control and identity",
        description:
          "Role-based access control, least-privilege permissions, and secure authentication flows across systems.",
      },
      {
        title: "Secure API and integration design",
        description:
          "Authentication, rate limiting, and input validation built into every integration point.",
      },
      {
        title: "Ongoing monitoring readiness",
        description:
          "Logging and alerting foundations so incidents are visible instead of discovered after the fact.",
      },
    ],
    process: [
      {
        step: "01",
        title: "Assess exposure",
        description:
          "Review the current systems, infrastructure, and integrations to understand what is actually exposed and how.",
      },
      {
        step: "02",
        title: "Prioritise by risk",
        description:
          "Rank findings by real business impact rather than theoretical severity alone.",
      },
      {
        step: "03",
        title: "Remediate",
        description:
          "Fix access control, configuration, and code-level issues in order of priority.",
      },
      {
        step: "04",
        title: "Harden and verify",
        description:
          "Apply infrastructure hardening and verify fixes against the original findings.",
      },
      {
        step: "05",
        title: "Document and monitor",
        description:
          "Leave the business with clear documentation and a foundation for ongoing monitoring.",
      },
    ],
    technologies: [
      "OWASP Top 10 methodology",
      "OAuth 2.0 / OIDC",
      "Role-based access control (RBAC)",
      "TLS & secure API gateways",
      "Cloud IAM (AWS / GCP / Azure)",
      "Secrets management",
      "Rate limiting & WAF configuration",
      "Audit logging",
    ],
    useCases: [
      "A business launching a customer-facing platform that needs to be secure from day one.",
      "A company that has grown quickly and needs its existing systems assessed and hardened.",
      "A team integrating third-party APIs that needs those integration points secured properly.",
      "A business that needs role-based access control across internal systems.",
    ],
    faqs: [
      {
        question: "Do you perform penetration testing?",
        answer:
          "I perform application and infrastructure security assessments focused on architecture, access control, and common vulnerability classes. Scope is defined clearly with the client before any engagement.",
      },
      {
        question: "Is this only for large companies?",
        answer:
          "No. Small and growing businesses are frequently the least protected, since security is often skipped under time pressure. The practices applied here scale down sensibly to smaller systems.",
      },
      {
        question: "Can you secure a system someone else built?",
        answer:
          "Yes. Reviewing and hardening existing systems — including ones built by other developers or agencies — is a core part of this service.",
      },
      {
        question: "Will this guarantee we are never breached?",
        answer:
          "No security practice can offer an absolute guarantee, and honest security work does not claim otherwise. The goal is to reduce real risk and exposure to the lowest practical level.",
      },
    ],
    pillars: [
      {
        slug: "application-security",
        name: "Application Security",
        tagline: "Security designed into the software itself.",
        summary:
          "Authentication, authorization, and vulnerability review built into your applications and APIs.",
      },
      {
        slug: "infrastructure-hardening",
        name: "Infrastructure Hardening",
        tagline: "Reduce the attack surface of your cloud infrastructure.",
        summary:
          "Locking down access, network exposure, and configuration across your cloud environment.",
      },
    ],
    relatedSlugs: ["cloud-devops", "software-saas"],
  },
  {
    slug: "cloud-devops",
    name: "Cloud & DevOps",
    shortName: "Cloud & DevOps",
    tagline: "Infrastructure that scales without babysitting.",
    heroDescription:
      "Cloud architecture, deployment pipelines, and infrastructure automation that keep your systems reliable, observable, and easy to ship changes to.",
    overview: [
      "Infrastructure should be something you rarely think about — not a source of late-night incidents. I design cloud environments and deployment pipelines that are reliable by default and simple enough for a small team to actually operate.",
      "That means proper environment separation, automated deployments instead of manual server access, monitoring that tells you about problems before customers do, and infrastructure defined as code so it can be reviewed and reproduced.",
      "The goal is infrastructure that scales with the business without requiring a dedicated operations team to keep it standing.",
    ],
    problems: [
      "Deployments are manual, risky, and depend on one person knowing the steps.",
      "There is no staging environment, so changes are tested in production.",
      "Infrastructure configuration exists only in someone's memory, not in code.",
      "No monitoring or alerting means outages are discovered by customers first.",
      "Cloud costs are unpredictable because resources are not managed deliberately.",
    ],
    capabilities: [
      {
        title: "Cloud architecture",
        description:
          "Environment design across AWS, GCP, or Azure suited to the actual scale and needs of the business.",
      },
      {
        title: "CI/CD pipelines",
        description:
          "Automated build, test, and deployment pipelines that remove manual, error-prone release steps.",
      },
      {
        title: "Infrastructure as code",
        description:
          "Infrastructure defined and version-controlled so it can be reviewed, reproduced, and recovered.",
      },
      {
        title: "Containerization",
        description:
          "Docker-based packaging for consistent environments from local development through to production.",
      },
      {
        title: "Monitoring and alerting",
        description:
          "Observability set up so issues are surfaced early, before they become customer-facing outages.",
      },
      {
        title: "Cost and performance optimisation",
        description:
          "Right-sizing infrastructure and cleaning up unused resources to keep cloud spend predictable.",
      },
    ],
    process: [
      {
        step: "01",
        title: "Audit current infrastructure",
        description:
          "Review existing environments, deployment process, and pain points.",
      },
      {
        step: "02",
        title: "Design the target architecture",
        description:
          "Plan environment separation, deployment flow, and monitoring appropriate to the scale of the business.",
      },
      {
        step: "03",
        title: "Automate deployment",
        description:
          "Build CI/CD pipelines so releases are consistent, tested, and no longer manual.",
      },
      {
        step: "04",
        title: "Set up observability",
        description:
          "Add monitoring and alerting so the team knows about issues immediately.",
      },
      {
        step: "05",
        title: "Document and hand over",
        description:
          "Leave the infrastructure documented and reproducible, not dependent on a single person.",
      },
    ],
    technologies: [
      "AWS / GCP / Azure",
      "Docker",
      "GitHub Actions / GitLab CI",
      "Terraform",
      "NGINX",
      "PostgreSQL / Redis",
      "Cloudflare",
      "Vercel",
    ],
    useCases: [
      "A growing platform that has outgrown manual, one-person deployments.",
      "A team that needs staging and production environments properly separated.",
      "A business that wants deployment automated so releases are safer and faster.",
      "A company that needs cloud spend brought under control and made predictable.",
    ],
    faqs: [
      {
        question: "Which cloud provider do you work with?",
        answer:
          "Architecture is chosen based on the project's needs rather than a fixed preference — AWS, GCP, Azure, and platforms like Vercel are all used depending on what fits best.",
      },
      {
        question: "Can you improve our existing infrastructure without a full rebuild?",
        answer:
          "In most cases, yes. Infrastructure work is usually incremental — automating deployments, adding monitoring, and hardening configuration rather than starting from zero.",
      },
      {
        question: "Do you offer ongoing infrastructure support?",
        answer:
          "Yes, this can be scoped as an ongoing engagement once the initial architecture and automation are in place.",
      },
    ],
    pillars: [
      {
        slug: "cloud-architecture",
        name: "Cloud Architecture",
        tagline: "Environments designed for how you actually operate.",
        summary:
          "Cloud environment design suited to the real scale and needs of the business.",
      },
      {
        slug: "devops-automation",
        name: "DevOps Automation",
        tagline: "Deployments you don't have to think about.",
        summary:
          "CI/CD pipelines and infrastructure as code that make shipping changes safe and repeatable.",
      },
    ],
    relatedSlugs: ["cybersecurity", "software-saas"],
  },
  {
    slug: "web-experiences",
    name: "Web Experiences",
    shortName: "Web Experiences",
    tagline: "Websites that feel like the product they represent.",
    heroDescription:
      "Web applications and immersive websites — including 3D, WebGL, and motion-driven experiences — designed with the same precision as the software behind them.",
    overview: [
      "The front end is where the business is judged first. A slow, generic website undersells serious engineering happening behind it.",
      "I build web applications and immersive marketing experiences — including WebGL and 3D-driven sites — with strong UI/UX foundations, real performance discipline, and design that matches the quality of the systems underneath.",
      "Every experience is engineered, not templated: accessible, responsive, and fast, whether it is a functional web application or a cinematic 3D showcase.",
    ],
    problems: [
      "The website looks and feels generic compared to the quality of the underlying business.",
      "Marketing sites are slow, hurting both user experience and search visibility.",
      "Web applications are difficult to use because UX was never properly designed.",
      "There is no distinct visual identity — the site could belong to any competitor.",
      "Immersive or interactive ideas are dismissed as too complex or expensive to build well.",
    ],
    capabilities: [
      {
        title: "Web application development",
        description:
          "Functional, fast, accessible web applications built with modern frameworks and real UX discipline.",
      },
      {
        title: "Immersive & 3D websites",
        description:
          "WebGL and Three.js-driven experiences — scroll-controlled 3D scenes, custom shaders, and cinematic motion.",
      },
      {
        title: "UI/UX and product design",
        description:
          "Interface design grounded in usability and a distinct visual identity, not generic templates.",
      },
      {
        title: "Performance engineering",
        description:
          "Core Web Vitals, load performance, and rendering optimisation treated as first-class requirements.",
      },
      {
        title: "Motion and interaction design",
        description:
          "Scroll-driven storytelling, transitions, and micro-interactions that support the content rather than distract from it.",
      },
      {
        title: "Technical SEO foundations",
        description:
          "Server-rendered content, structured data, and clean architecture so immersive sites remain fully discoverable.",
      },
    ],
    process: [
      {
        step: "01",
        title: "Define the narrative",
        description:
          "Establish what the site needs to communicate and in what order before any visual or technical decisions are made.",
      },
      {
        step: "02",
        title: "Design the system",
        description:
          "Build the visual language, typography, and interaction patterns as a coherent system.",
      },
      {
        step: "03",
        title: "Engineer the experience",
        description:
          "Build the front end — including any 3D, shader, or motion work — with performance and accessibility built in from the start.",
      },
      {
        step: "04",
        title: "Optimise",
        description:
          "Tune performance, responsiveness, and Core Web Vitals across devices.",
      },
      {
        step: "05",
        title: "Launch and refine",
        description:
          "Ship with proper SEO foundations in place and refine based on real usage.",
      },
    ],
    technologies: [
      "Next.js & React",
      "TypeScript",
      "Three.js & React Three Fiber",
      "GSAP & ScrollTrigger",
      "WebGL & GLSL",
      "Tailwind CSS",
      "Framer Motion",
      "Lighthouse / Core Web Vitals tooling",
    ],
    useCases: [
      "A brand that wants a flagship website that feels as advanced as the technology it sells.",
      "A product that needs a genuinely usable, well-designed web application, not just a landing page.",
      "A company whose current site loads slowly and ranks poorly despite good content.",
      "A team that wants an immersive 3D experience without sacrificing accessibility or SEO.",
    ],
    faqs: [
      {
        question: "Will a 3D or WebGL website hurt my SEO?",
        answer:
          "Not if it is built correctly. Content is server-rendered as real HTML alongside the 3D layer, so search engines see full text content regardless of what is happening in the canvas.",
      },
      {
        question: "Will a 3D site be slow on mobile?",
        answer:
          "Immersive experiences are built with adaptive quality — reduced particle counts, capped pixel ratios, and simplified effects on lower-powered devices — plus a static fallback if WebGL is unavailable.",
      },
      {
        question: "Do you design as well as build?",
        answer:
          "Yes. Design and engineering are handled together so the visual system and the technical implementation stay aligned throughout.",
      },
      {
        question: "Can you build a standard web application without the 3D elements?",
        answer:
          "Yes — immersive 3D is one option, not a requirement. Many projects call for a clean, fast, well-designed web application without WebGL, and that is built with the same care.",
      },
    ],
    pillars: [
      {
        slug: "web-applications",
        name: "Web Applications",
        tagline: "Fast, accessible, genuinely usable products.",
        summary:
          "Functional web applications built with modern frameworks and real UX discipline.",
      },
      {
        slug: "immersive-experiences",
        name: "Immersive Experiences",
        tagline: "WebGL and 3D storytelling that stays fast and accessible.",
        summary:
          "Scroll-controlled 3D scenes, custom shaders, and cinematic motion design.",
      },
      {
        slug: "ui-ux-design",
        name: "UI/UX & Product Design",
        tagline: "Interfaces designed around real usability.",
        summary:
          "Interface and product design grounded in usability and a distinct visual identity.",
      },
    ],
    relatedSlugs: ["software-saas", "ai-automation"],
  },
];

export function getServiceBySlug(slug: string): Service | undefined {
  return services.find((service) => service.slug === slug);
}
