import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { ChapterScene } from "@/components/three/ChapterScene";
import { Reveal } from "@/components/ui/Reveal";
import { buildMetadata } from "@/lib/seo";
import { webPageSchema } from "@/lib/schema";
import { projects } from "@/data/projects";

export const metadata: Metadata = buildMetadata({
  title: "Projects",
  description:
    "Selected GRIDKEEP projects, including RAFANA Digital Platform, the AI Customer Engagement Platform, and the GRIDKEEP Digital Experience.",
  path: "/projects",
});

export default function ProjectsPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "GRIDKEEP Projects",
          description: "Selected GRIDKEEP projects.",
          path: "/projects",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Projects", path: "/projects" }]} />
      <PageHero
        eyebrow="Work"
        title="Selected projects."
        description="A small, honest selection of what GRIDKEEP has built — including work still in progress."
      />

      <section className="mx-auto grid max-w-[1600px] grid-cols-1 gap-6 px-6 pb-32 md:grid-cols-3 md:px-10">
        {projects.map((project, index) => (
          <Reveal key={project.slug} delay={index * 0.05}>
            <Link
              href={`/projects/${project.slug}`}
              className="group relative flex h-[440px] flex-col justify-end overflow-hidden border border-line bg-black transition-colors hover:border-orange/60"
            >
              <ChapterScene scene={project.scene} className="absolute inset-0" postFX={false} interactive={false} />
              <div className="relative z-10 bg-gradient-to-t from-black via-black/85 to-transparent p-6">
                <span className="font-mono text-[10px] uppercase tracking-widest2 text-orange">
                  {project.status}
                </span>
                <h2 className="mt-2 font-display text-2xl text-warm group-hover:text-orange-bright">
                  {project.name}
                </h2>
                <p className="mt-2 text-sm text-muted">{project.summary}</p>
              </div>
            </Link>
          </Reveal>
        ))}
      </section>
    </>
  );
}
