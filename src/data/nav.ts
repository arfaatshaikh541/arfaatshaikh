import type { NavItem } from "@/types";

export const navItems: NavItem[] = [
  { label: "Home", href: "/" },
  {
    label: "Services",
    href: "/services",
    children: [
      { label: "AI & AI Agents", href: "/services/ai-agents", description: "Intelligent systems that think, learn and adapt." },
      { label: "Business Automation", href: "/services/automation", description: "Automate processes and eliminate operational friction." },
      { label: "Custom Software & SaaS", href: "/services/software-saas", description: "Scalable software and SaaS platforms built for growth." },
      { label: "Cybersecurity", href: "/services/cybersecurity", description: "Protect systems, data and digital infrastructure." },
      { label: "Cloud & DevOps", href: "/services/cloud-devops", description: "Secure, scalable and high-performance infrastructure." },
      { label: "Business Systems", href: "/services/business-systems", description: "CRM, ERP, APIs and data systems that work in sync." },
      { label: "Web Experiences", href: "/services/web-experiences", description: "Immersive, technically engineered digital experiences." },
    ],
  },
  { label: "Projects", href: "/projects" },
  { label: "Industries", href: "/industries" },
  { label: "GRIDKEEP System", href: "/gridkeep-system" },
  { label: "Insights", href: "/insights" },
  { label: "About", href: "/about" },
  { label: "Contact", href: "/contact" },
];

export const footerServiceLinks = navItems.find((n) => n.label === "Services")!.children!.map((c) => ({
  label: c.label,
  href: c.href,
}));

export const footerCompanyLinks = [
  { label: "About", href: "/about" },
  { label: "GRIDKEEP System", href: "/gridkeep-system" },
  { label: "Projects", href: "/projects" },
  { label: "Industries", href: "/industries" },
  { label: "Insights", href: "/insights" },
  { label: "Contact", href: "/contact" },
];

export const footerLegalLinks = [
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
];
