import { projects } from "@/data/projects";
import SectionLabel from "@/components/ui/SectionLabel";
import ProjectCard from "@/components/ui/ProjectCard";
import { LinkButton } from "@/components/ui/Button";

export default function Projects() {
  return (
    <section className="relative border-t border-line bg-black-near py-20 md:py-28" aria-labelledby="projects-heading">
      <div className="mx-auto max-w-[1440px] px-6 md:px-10">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-[0.85fr_2fr] md:gap-14">
          <div>
            <SectionLabel>Projects</SectionLabel>
            <h2 id="projects-heading" className="gk-heading mt-5 text-4xl text-warmwhite sm:text-5xl">
              SOLUTIONS BUILT FOR REAL <span className="text-orange-primary">IMPACT.</span>
            </h2>
            <p className="mt-5 max-w-sm text-sm leading-relaxed text-muted">
              From client platforms to internal products, we build systems that solve real business challenges.
            </p>
            <LinkButton href="/projects" variant="secondary" className="mt-8">
              View All Projects →
            </LinkButton>
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard key={project.slug} project={project} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
