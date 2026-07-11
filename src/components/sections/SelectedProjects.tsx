import Link from "next/link";
import { projects } from "@/data/projects";

export function SelectedProjects() {
  return (
    <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="projects-heading">
      <div className="container-edge flex flex-col justify-between gap-6 md:flex-row md:items-end">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Selected Work
          </p>
          <h2 id="projects-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
            Projects
          </h2>
        </div>
        <Link
          href="/projects"
          className="font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:text-[var(--color-blood-red)]"
        >
          View all projects →
        </Link>
      </div>

      <div className="container-edge mt-16 grid gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] md:grid-cols-3">
        {projects.map((project) => (
          <Link
            key={project.slug}
            href={`/projects/${project.slug}`}
            className="group flex flex-col justify-between bg-black p-8 transition-colors hover:bg-[var(--color-surface)]"
          >
            <div>
              <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--color-blood-red)]">
                {project.status}
              </span>
              <h3 className="mt-4 font-display text-2xl uppercase leading-tight text-[var(--color-off-white)]">
                {project.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">
                {project.summary}
              </p>
            </div>
            <span
              aria-hidden="true"
              className="mt-8 inline-block font-mono text-sm text-[var(--color-muted)] transition-transform group-hover:translate-x-1 group-hover:text-[var(--color-blood-red)]"
            >
              View project →
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
