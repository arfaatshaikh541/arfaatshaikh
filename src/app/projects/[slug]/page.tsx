import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { ChapterScene } from "@/components/three/ChapterScene";
import { Reveal } from "@/components/ui/Reveal";
import { ButtonLink } from "@/components/ui/Button";
import { buildMetadata } from "@/lib/seo";
import { creativeWorkSchema, softwareApplicationSchema } from "@/lib/schema";
import { getProjectBySlug, projects } from "@/data/projects";
import { getServiceBySlug } from "@/data/services";

export function generateStaticParams() {
  return projects.map((project) => ({ slug: project.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const project = getProjectBySlug(slug);
  if (!project) return {};
  return buildMetadata({
    title: project.name,
    description: project.summary,
    path: `/projects/${project.slug}`,
  });
}

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const project = getProjectBySlug(slug);
  if (!project) notFound();

  const relatedServices = project.relatedServices
    .map((slug) => getServiceBySlug(slug))
    .filter(Boolean);

  return (
    <>
      <JsonLd
        data={[
          creativeWorkSchema({ name: project.name, description: project.description, slug: project.slug }),
          softwareApplicationSchema({ name: project.name, description: project.summary, slug: project.slug }),
        ]}
      />
      <Breadcrumbs
        items={[
          { name: "Home", path: "/" },
          { name: "Projects", path: "/projects" },
          { name: project.name, path: `/projects/${project.slug}` },
        ]}
      />

      <div className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 opacity-70">
          <ChapterScene scene={project.scene} interactive className="h-full w-full" />
        </div>
        <PageHero eyebrow={project.status} title={project.name} description={project.summary} />
      </div>

      <section className="mx-auto grid max-w-[1600px] grid-cols-1 gap-16 px-6 pb-32 md:grid-cols-3 md:px-10">
        <div className="md:col-span-2">
          <Reveal>
            <h2 className="font-display text-2xl text-warm">About this project</h2>
            <p className="mt-4 text-muted">{project.description}</p>
          </Reveal>
        </div>
        <aside>
          <Reveal delay={0.08}>
            <div className="border border-line p-6">
              <span className="font-mono text-xs uppercase tracking-widest2 text-orange">Technology</span>
              <ul className="mt-4 flex flex-col gap-2">
                {project.technologies.map((tech) => (
                  <li key={tech} className="text-sm text-warm">
                    {tech}
                  </li>
                ))}
              </ul>

              {relatedServices.length > 0 && (
                <>
                  <span className="mt-8 block font-mono text-xs uppercase tracking-widest2 text-orange">
                    Related services
                  </span>
                  <ul className="mt-4 flex flex-col gap-2">
                    {relatedServices.map((service) => (
                      <li key={service!.slug}>
                        <Link href={`/services/${service!.slug}`} className="text-sm text-warm hover:text-orange">
                          {service!.shortName}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              <div className="mt-8">
                <ButtonLink href="/contact" className="w-full text-center">
                  Start a similar project
                </ButtonLink>
              </div>
            </div>
          </Reveal>
        </aside>
      </section>
    </>
  );
}
