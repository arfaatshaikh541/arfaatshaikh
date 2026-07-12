import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import ProjectPrototypeStage from "@/components/sections/ProjectPrototypeStage";
import { PROJECTS, getProjectBySlug } from "@/lib/projects-data";
import { getServiceBySlug } from "@/lib/services-data";
import { webPageSchema } from "@/lib/schema";

export function generateStaticParams() {
  return PROJECTS.map((p) => ({ slug: p.slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const project = getProjectBySlug(slug);
  if (!project) return {};
  return {
    title: project.name,
    description: project.summary,
    alternates: { canonical: `/projects/${project.slug}` },
    openGraph: { url: `/projects/${project.slug}`, title: project.name, description: project.summary },
  };
}

export default async function ProjectPage({ params }: Props) {
  const { slug } = await params;
  const project = getProjectBySlug(slug);
  if (!project) notFound();

  const relatedServices = project.services.map((s) => getServiceBySlug(s)).filter(Boolean);

  return (
    <>
      <JsonLd data={webPageSchema({ name: project.name, description: project.summary, path: `/projects/${project.slug}` })} />
      <Breadcrumbs
        items={[
          { name: "Home", path: "/" },
          { name: "Projects", path: "/projects" },
          { name: project.name, path: `/projects/${project.slug}` },
        ]}
      />

      <section className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-16 sm:px-8">
        <div className="mx-auto grid max-w-[1600px] items-center gap-12 lg:grid-cols-2 lg:gap-16">
          <div>
            <span className="font-mono-tech text-[0.7rem] uppercase tracking-[0.14em] text-gk-orange">{project.status}</span>
            <h1 className="font-display mt-4 text-4xl font-bold uppercase leading-tight sm:text-5xl">{project.name}</h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-gk-grey">{project.description}</p>
          </div>
          <ProjectPrototypeStage slug={project.slug} title={project.prototypeLabel} description={project.prototypeDescription} />
        </div>
      </section>

      <section className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">{project.prototypeLabel}</p>
          <h2 className="font-display mt-3 max-w-2xl text-3xl font-bold uppercase sm:text-4xl">Capabilities</h2>
          <ul className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {project.capabilities.map((cap) => (
              <li key={cap} className="gk-panel flex items-start gap-3 border border-gk-steel p-5 text-sm text-gk-grey">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 bg-gk-orange" aria-hidden="true" />
                {cap}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {relatedServices.length > 0 && (
        <section className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
          <div className="mx-auto max-w-[1600px]">
            <p className="gk-eyebrow">Systems Applied</p>
            <h2 className="font-display mt-3 text-3xl font-bold uppercase sm:text-4xl">Related services</h2>
            <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {relatedServices.map((service) => (
                <Link
                  key={service!.slug}
                  href={`/services/${service!.slug}`}
                  className="gk-panel border border-gk-steel p-6 transition-colors hover:border-gk-orange/60"
                >
                  <span className="gk-eyebrow">{service!.index}</span>
                  <h3 className="font-display mt-2 text-lg font-semibold text-gk-white">{service!.name}</h3>
                  <p className="mt-2 text-sm text-gk-grey">{service!.tagline}</p>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="bg-gk-black px-5 py-24 text-center sm:px-8">
        <h2 className="font-display mx-auto max-w-2xl text-3xl font-bold uppercase sm:text-4xl">
          Building something <span className="gk-orange-text">similar?</span>
        </h2>
        <div className="mt-8">
          <Link href="/contact" className="gk-btn gk-btn-primary">
            Open a Project Channel
          </Link>
        </div>
      </section>
    </>
  );
}
