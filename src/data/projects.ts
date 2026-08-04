import type { Project } from "@/types";

export const projects: Project[] = [
  {
    slug: "rafana-digital-platform",
    title: "RAFANA Digital Platform",
    category: "Client Platform · Professional Services",
    status: "Client Platform",
    year: "2024",
    summary:
      "A digital platform for a UAE auditing, taxation, accounting, and advisory firm.",
    description: [
      "RAFANA required a digital presence and set of internal systems capable of representing a serious professional services firm operating across auditing, taxation, accounting, and advisory work in the UAE.",
      "The platform was built to communicate credibility and expertise clearly to prospective clients, while giving the firm a structured way to present its services, industries served, and ways for clients to get in touch and begin an engagement.",
      "The build focused on clarity, performance, and a professional visual system appropriate to a regulated advisory business — prioritising trust and information architecture over decoration.",
    ],
    role: "Design & full-stack development",
    industry: "Auditing, Taxation & Advisory",
    capabilities: [
      "Web application development",
      "UI/UX design",
      "Content architecture",
      "Technical SEO",
    ],
    technologies: ["Next.js", "TypeScript", "Tailwind CSS", "Node.js"],
    highlights: [
      "Structured service architecture across auditing, tax, accounting, and advisory offerings.",
      "Professional design system suited to a regulated financial services brand.",
      "Performance and SEO foundations built in from the start.",
    ],
    image: "/images/projects/rafana.svg",
  },
  {
    slug: "ai-customer-engagement-platform",
    title: "AI Customer Engagement Platform",
    category: "Internal Product · Multi-Tenant SaaS",
    status: "In Development",
    year: "2024–2025",
    summary:
      "A multi-tenant AI customer engagement system for salons, clinics, gyms, real estate companies, and service businesses.",
    description: [
      "Service businesses — salons, clinics, gyms, real estate agencies — share a common problem: customer enquiries and bookings arrive constantly, often outside working hours, and inconsistent follow-up costs them business.",
      "This platform is a multi-tenant system that gives each business its own configured AI agent, trained on that business's services, availability, and tone, capable of handling enquiries, qualifying leads, and assisting with bookings across web and messaging channels.",
      "The architecture is built for multi-tenancy from the ground up: each client's data, configuration, and conversation history are isolated within a shared platform, allowing the system to scale across many businesses without compromising data separation.",
    ],
    role: "Product architecture & full-stack development",
    industry: "Multi-industry (salons, clinics, gyms, real estate, services)",
    capabilities: [
      "AI agent design",
      "Multi-tenant SaaS architecture",
      "Business automation",
      "API integrations",
    ],
    technologies: [
      "Next.js",
      "TypeScript",
      "Node.js",
      "PostgreSQL",
      "OpenAI API",
      "WhatsApp Business API",
    ],
    highlights: [
      "Multi-tenant architecture supporting isolated configuration per client business.",
      "AI agents scoped per business context, services, and tone of voice.",
      "Automated lead qualification and booking assistance across channels.",
    ],
    image: "/images/projects/ai-engagement.svg",
  },
  {
    slug: "gridkeep-digital-experience",
    title: "GRIDKEEP Digital Experience",
    category: "Internal Product · Technology Brand",
    status: "In Development",
    year: "2025",
    summary:
      "A founder-led technology brand and digital experience focused on AI, software, cybersecurity, cloud, and automation.",
    description: [
      "GRIDKEEP is the technology brand behind the engineering work described across this site — a founder-led studio for AI, custom software, cybersecurity, cloud infrastructure, and automation.",
      "The digital experience for GRIDKEEP is built to reflect the same standard applied to client work: an engineered, cinematic presence rather than a generic agency template, demonstrating the technical capability of the studio through its own site.",
      "As GRIDKEEP's service lines and case studies grow, the platform is designed to scale — from a founder-led brand presence today toward a fuller studio platform over time.",
    ],
    role: "Founder, design & full-stack development",
    industry: "Technology & Engineering Services",
    capabilities: [
      "Brand & digital experience design",
      "Immersive web development",
      "Systems architecture",
      "Technical SEO",
    ],
    technologies: [
      "Next.js",
      "TypeScript",
      "Three.js",
      "React Three Fiber",
      "GSAP",
    ],
    highlights: [
      "Founder-led technology brand spanning AI, software, security, and cloud services.",
      "Digital experience engineered to demonstrate the studio's own technical standard.",
      "Architecture designed to scale as GRIDKEEP's service lines and case studies grow.",
    ],
    image: "/images/projects/gridkeep.svg",
  },
];

export function getProjectBySlug(slug: string): Project | undefined {
  return projects.find((project) => project.slug === slug);
}
