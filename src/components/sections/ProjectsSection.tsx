import Link from "next/link";
import { projects } from "@/data/projects";
import { ChapterScene } from "@/components/three/ChapterScene";
import { Reveal } from "@/components/ui/Reveal";
import { SectionLabel } from "@/components/ui/SectionLabel";

export function ProjectsSection() {
  return (
    <section className="relative bg-graphite py-32" aria-labelledby="projects-heading">
      <div className="mx-auto max-w-[1600px] px-6 md:px-10">
        <Reveal>
          <SectionLabel index="11" label="Selected projects" />
        </Reveal>
        <Reveal delay={0.08}>
          <h2 id="projects-heading" className="mt-6 max-w-2xl text-balance font-display text-4xl text-warm md:text-5xl">
            Real systems, built and running.
          </h2>
        </Reveal>

        <div className="mt-16 grid grid-cols-1 gap-6 md:grid-cols-3">
          {projects.map((project) => (
            <Link
              key={project.slug}
              href={`/projects/${project.slug}`}
              className="group relative flex h-[420px] flex-col justify-end overflow-hidden border border-line bg-black transition-colors hover:border-orange/60"
            >
              <ChapterScene
                scene={project.scene}
                className="absolute inset-0"
                postFX={false}
                interactive={false}
              />
              <div className="relative z-10 bg-gradient-to-t from-black via-black/80 to-transparent p-6">
                <span className="font-mono text-[10px] uppercase tracking-widest2 text-orange">
                  {project.status}
                </span>
                <h3 className="mt-2 font-display text-xl text-warm group-hover:text-orange-bright">
                  {project.name}
                </h3>
                <p className="mt-2 text-sm text-muted">{project.summary}</p>
              </div>
            </Link>
          ))}
        </div>

        <Reveal delay={0.1}>
          <div className="mt-10">
            <Link href="/projects" className="font-mono text-xs uppercase tracking-widest2 text-orange hover:text-orange-bright">
              View all projects →
            </Link>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
