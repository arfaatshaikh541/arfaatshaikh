import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import SectionLabel from "@/components/ui/SectionLabel";
import { LinkButton } from "@/components/ui/Button";
import SceneCanvas from "@/components/three/SceneCanvas";
import PrototypeModel from "@/components/three/PrototypeModel";
import ContactPortal from "@/components/sections/ContactPortal";
import { projects } from "@/data/projects";

interface ProjectPageProps {
  params: { slug: string };
}

export function generateStaticParams() {
  return projects.map((p) => ({ slug: p.slug }));
}

export function generateMetadata({ params }: ProjectPageProps): Metadata {
  const project = projects.find((p) => p.slug === params.slug);
  if (!project) return buildMetadata({ title: "Project", path: `/projects/${params.slug}` });
  return buildMetadata({
    title: project.title,
    description: project.description,
    path: `/projects/${project.slug}`,
  });
}

export default function ProjectDetailPage({ params }: ProjectPageProps) {
  const project = projects.find((p) => p.slug === params.slug);
  if (!project) notFound();

  const crumbs = [
    { name: "Home", path: "/" },
    { name: "Projects", path: "/projects" },
    { name: project.title, path: `/projects/${project.slug}` },
  ];

  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <Breadcrumbs items={crumbs} />

      <section className="relative overflow-hidden border-b border-line bg-black pb-16 pt-14 md:pb-24 md:pt-20">
        <div className="pointer-events-none absolute inset-0 bg-grid-lines bg-[size:52px_52px] opacity-[0.25]" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-[1440px] grid-cols-1 items-center gap-10 px-6 md:grid-cols-[1.2fr_0.8fr] md:px-10">
          <div>
            <span className="w-fit border border-orange-bright/40 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-orange-bright">
              {project.status}
            </span>
            <h1 className="gk-heading mt-5 text-4xl text-warmwhite sm:text-5xl md:text-6xl">{project.title}</h1>
            <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted md:text-base">{project.description}</p>
            <div className="mt-7 flex flex-wrap gap-2">
              {project.focus.map((f) => (
                <span key={f} className="border border-line px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted">
                  {f}
                </span>
              ))}
            </div>
            <LinkButton href="/projects" variant="secondary" className="mt-9">
              ← All Projects
            </LinkButton>
          </div>
          <div className="relative mx-auto h-[280px] w-full max-w-[420px] md:h-[380px]">
            <SceneCanvas eager camera={{ position: [0, 0, 6.5], fov: 40 }} posterLabel={project.title}>
              <PrototypeModel variant={project.model} scale={0.95} />
            </SceneCanvas>
          </div>
        </div>
      </section>

      <section className="border-b border-line bg-black-near py-16 md:py-24">
        <div className="mx-auto max-w-[1440px] px-6 md:px-10">
          <SectionLabel>Overview</SectionLabel>
          <p className="mt-6 max-w-2xl text-sm leading-relaxed text-warmwhite/80 md:text-base">{project.summary}</p>
        </div>
      </section>

      <ContactPortal />
    </>
  );
}
