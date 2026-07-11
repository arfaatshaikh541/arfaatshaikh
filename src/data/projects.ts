import type { Project } from "@/types";

export const projects: Project[] = [
  {
    slug: "rafana-digital-platform",
    title: "RAFANA Digital Platform",
    status: "Client Platform",
    summary: "A digital platform for a UAE auditing, taxation, real estate and advisory firm.",
    description:
      "GRIDKEEP engineered a digital platform for RAFANA covering client-facing service presentation and internal operational workflows across auditing, taxation, real estate and advisory services — built as a single coherent system rather than disconnected pages.",
    model: "architecture",
    focus: ["Custom Software", "Business Systems"],
  },
  {
    slug: "ai-customer-engagement-platform",
    title: "AI Customer Engagement Platform",
    status: "In Development",
    summary: "A multi-tenant AI customer engagement system for salons, clinics, real estate and service businesses.",
    description:
      "An AI-driven engagement platform currently in development, designed to give service businesses — salons, clinics, real estate teams and similar operators — a shared engine for automated customer communication, scheduling logic and follow-up.",
    model: "neural",
    focus: ["AI & AI Agents", "Business Automation"],
  },
  {
    slug: "gridkeep-digital-experience",
    title: "GRIDKEEP Digital Experience",
    status: "Internal Product",
    summary: "The digital brand and experience platform for GRIDKEEP itself.",
    description:
      "This website — an internally engineered, systems-first digital experience combining real-time 3D, motion design and production software architecture to represent how GRIDKEEP builds for its clients.",
    model: "reactor",
    focus: ["Web Experiences", "Custom Software"],
  },
];
