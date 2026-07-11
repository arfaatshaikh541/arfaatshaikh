export interface HeroChapter {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  cta?: { label: string; href: string };
}

export const heroChapters: HeroChapter[] = [
  {
    id: "dormant",
    eyebrow: "Arfaat Shaikh · Creative Engineer",
    title: "Something is\nbuilt to wake.",
    description:
      "Based in the United Arab Emirates. Founder of GRIDKEEP. I build the systems that most companies are afraid to build.",
  },
  {
    id: "awakening",
    eyebrow: "Awakening",
    title: "Dormant systems,\nturned into working products.",
    description:
      "Every engagement starts the same way — understanding what's actually broken before writing a single line of code.",
  },
  {
    id: "ai-automation",
    eyebrow: "01 · Intelligence",
    title: "AI Agents\n& Automation",
    description:
      "Agents that understand your business and act inside it — connected to your real tools, not a demo.",
    cta: { label: "Explore AI & Automation", href: "/services/ai-automation" },
  },
  {
    id: "automation",
    eyebrow: "02 · Flow",
    title: "Business\nAutomation",
    description:
      "Removing the manual steps between the tools you already use, so information moves without anyone re-typing it.",
    cta: { label: "See how it works", href: "/services/ai-automation" },
  },
  {
    id: "software",
    eyebrow: "03 · Structure",
    title: "Custom Software\n& SaaS",
    description:
      "Systems built around how your business actually works — CRM, ERP, dashboards, and multi-tenant platforms.",
    cta: { label: "Explore Software & SaaS", href: "/services/software-saas" },
  },
  {
    id: "cybersecurity",
    eyebrow: "04 · Defense",
    title: "Cybersecurity",
    description:
      "Security built into the architecture from the first line of code — not bolted on after something breaks.",
    cta: { label: "Explore Cybersecurity", href: "/services/cybersecurity" },
  },
  {
    id: "cloud",
    eyebrow: "05 · Infrastructure",
    title: "Cloud\n& DevOps",
    description:
      "Infrastructure and deployment pipelines that scale quietly, without a dedicated operations team to keep them standing.",
    cta: { label: "Explore Cloud & DevOps", href: "/services/cloud-devops" },
  },
  {
    id: "gridkeep",
    eyebrow: "GRIDKEEP",
    title: "One system.\nEvery discipline.",
    description:
      "GRIDKEEP is the technology studio behind this work — AI, software, security, and cloud under one founder-led standard.",
    cta: { label: "Enter GRIDKEEP", href: "/gridkeep" },
  },
  {
    id: "contact",
    eyebrow: "Start a project",
    title: "Let's build\nwhat's next.",
    description:
      "If you have a system worth building properly, I want to hear about it.",
    cta: { label: "Start the conversation", href: "/contact" },
  },
];
