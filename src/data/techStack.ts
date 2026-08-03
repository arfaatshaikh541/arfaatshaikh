export interface TechStackGroup {
  label: string;
  description: string;
  items: string[];
}

export const techStackGroups: TechStackGroup[] = [
  {
    label: "Languages & Frameworks",
    description:
      "The default starting point for almost everything — typed, well-supported, and fast to hire around if a team ever needs to take a project over.",
    items: ["TypeScript", "React", "Next.js", "Node.js", "Python"],
  },
  {
    label: "AI & Automation",
    description:
      "Model providers and retrieval tooling for agents that read from and act inside real systems, not chat-only demos.",
    items: ["OpenAI API", "Anthropic API", "LangChain", "Vector Databases"],
  },
  {
    label: "Data & Systems",
    description:
      "Relational storage as the default, with caching and typed queries layered on rather than bolted on after something breaks.",
    items: ["PostgreSQL", "Prisma", "REST & GraphQL", "Redis"],
  },
  {
    label: "Cloud & DevOps",
    description:
      "Infrastructure and deployment pipelines chosen so systems keep running without a dedicated operations team watching them.",
    items: ["AWS", "Docker", "GitHub Actions", "Terraform", "Vercel"],
  },
  {
    label: "3D & Motion",
    description:
      "For the projects that call for it — real-time 3D and motion work like the hero on this site, not just static pages.",
    items: ["Three.js", "React Three Fiber", "GSAP", "WebGL"],
  },
];
