import Link from "next/link";
import { techStackGroups } from "@/data/techStack";

export function TechStackSection() {
  return (
    <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="stack-heading">
      <div className="container-edge flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Toolset
          </p>
          <h2 id="stack-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
            Technology Stack
          </h2>
        </div>
        <Link
          href="/tech-stack"
          className="inline-flex items-center gap-3 font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:text-[var(--color-blood-red)]"
        >
          View full stack →
        </Link>
      </div>

      <div className="container-edge mt-16 grid gap-10 md:grid-cols-5">
        {techStackGroups.map((group) => (
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
