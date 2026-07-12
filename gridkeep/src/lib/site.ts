export const SITE = {
  name: "GRIDKEEP",
  legalName: "GRIDKEEP",
  url: "https://gridkeep.com",
  founder: "Arfaat Shaikh",
  location: "United Arab Emirates",
  email: "hello@gridkeep.com",
  tagline: "We build the systems behind the business.",
  description:
    "GRIDKEEP is a founder-led technology systems company that designs and engineers AI systems, automation, custom software, cybersecurity, cloud infrastructure, business systems, and immersive web experiences.",
} as const;

export type NavLink = {
  label: string;
  href: string;
};

export const PRIMARY_NAV: NavLink[] = [
  { label: "Systems", href: "/gridkeep-system" },
  { label: "Services", href: "/services" },
  { label: "Projects", href: "/projects" },
  { label: "Industries", href: "/industries" },
  { label: "Insights", href: "/insights" },
  { label: "About", href: "/about" },
];

export const FOOTER_NAV: { title: string; links: NavLink[] }[] = [
  {
    title: "Services",
    links: [
      { label: "AI & AI Agents", href: "/services/ai-agents" },
      { label: "Business Automation", href: "/services/automation" },
      { label: "Custom Software", href: "/services/software-saas" },
      { label: "Cybersecurity", href: "/services/cybersecurity" },
      { label: "Cloud & DevOps", href: "/services/cloud-devops" },
      { label: "Business Systems", href: "/services/business-systems" },
      { label: "Web Experiences", href: "/services/web-experiences" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Projects", href: "/projects" },
      { label: "Industries", href: "/industries" },
      { label: "GRIDKEEP System", href: "/gridkeep-system" },
      { label: "Insights", href: "/insights" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Terms of Service", href: "/terms" },
    ],
  },
];
