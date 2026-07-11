import type { Project } from "@/types";

export const projects: Project[] = [
  {
    slug: "rafana-digital-platform",
    name: "RAFANA Digital Platform",
    status: "Client Platform",
    summary:
      "A digital platform for a UAE auditing, taxation, accounting, and advisory firm.",
    description:
      "GRIDKEEP designed and built the digital platform for RAFANA, a UAE-based auditing, taxation, accounting, and advisory firm. The platform gives the firm a professional digital presence and a structured way to present its audit, tax, accounting, and advisory services to clients across the UAE, engineered for clarity, credibility, and long-term maintainability.",
    technologies: ["Next.js", "TypeScript", "Custom CMS architecture", "SEO infrastructure"],
    relatedServices: ["software-saas", "web-experiences"],
    scene: "architecture",
  },
  {
    slug: "ai-customer-engagement-platform",
    name: "AI Customer Engagement Platform",
    status: "In Development",
    summary:
      "A multi-tenant AI customer engagement system for salons, clinics, gyms, real estate companies, and service businesses.",
    description:
      "A multi-tenant AI customer engagement platform in active development at GRIDKEEP, built to give salons, clinics, gyms, real estate companies, and other service businesses a shared engagement layer — AI-assisted booking, customer communication, and follow-up — without each business needing separate custom software.",
    technologies: ["AI agent orchestration", "Multi-tenant architecture", "Next.js", "Cloud infrastructure"],
    relatedServices: ["ai-agents", "software-saas", "automation"],
    scene: "neural",
  },
  {
    slug: "gridkeep-digital-experience",
    name: "GRIDKEEP Digital Experience",
    status: "Internal Product",
    summary: "The digital brand and experience platform for GRIDKEEP.",
    description:
      "The GRIDKEEP website itself — a fully custom, 3D-driven brand and experience platform built to demonstrate the engineering and design standard GRIDKEEP holds itself to: real-time WebGL systems, custom shaders, and scroll-driven storytelling built on Next.js and React Three Fiber.",
    technologies: ["Next.js", "React Three Fiber", "Three.js", "GSAP", "Custom GLSL shaders"],
    relatedServices: ["web-experiences", "software-saas"],
    scene: "command",
  },
];

export function getProjectBySlug(slug: string) {
  return projects.find((project) => project.slug === slug);
}
