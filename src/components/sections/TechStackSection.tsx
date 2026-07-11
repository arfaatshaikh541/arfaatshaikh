const STACK_GROUPS = [
  {
    label: "Languages & Frameworks",
    items: ["TypeScript", "React", "Next.js", "Node.js", "Python"],
  },
  {
    label: "AI & Automation",
    items: ["OpenAI API", "Anthropic API", "LangChain", "Vector Databases"],
  },
  {
    label: "Data & Systems",
    items: ["PostgreSQL", "Prisma", "REST & GraphQL", "Redis"],
  },
  {
    label: "Cloud & DevOps",
    items: ["AWS", "Docker", "GitHub Actions", "Terraform", "Vercel"],
  },
  {
    label: "3D & Motion",
    items: ["Three.js", "React Three Fiber", "GSAP", "WebGL"],
  },
];

export function TechStackSection() {
  return (
    <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="stack-heading">
      <div className="container-edge">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Toolset
        </p>
        <h2 id="stack-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          Technology Stack
        </h2>
      </div>

      <div className="container-edge mt-16 grid gap-10 md:grid-cols-5">
        {STACK_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="font-mono text-xs uppercase tracking-[0.1em] text-[var(--color-muted)]">
              {group.label}
            </p>
            <ul className="mt-4 space-y-2">
              {group.items.map((item) => (
                <li key={item} className="text-sm text-[var(--color-off-white)]">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
