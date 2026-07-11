import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import PageIntro from "@/components/sections/PageIntro";
import ProjectCard from "@/components/ui/ProjectCard";
import ContactPortal from "@/components/sections/ContactPortal";
import { projects } from "@/data/projects";

export const metadata = buildMetadata({
  title: "Projects",
  description:
    "GRIDKEEP projects: the RAFANA Digital Platform, an AI Customer Engagement Platform in development, and the GRIDKEEP Digital Experience itself.",
  path: "/projects",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "Projects", path: "/projects" },
];

export default function ProjectsPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <Breadcrumbs items={crumbs} />
      <PageIntro
        eyebrow="Projects"
        title={
          <>
            SOLUTIONS BUILT FOR REAL <span className="text-orange-primary">IMPACT.</span>
          </>
        }
        description="From client platforms to internal products, GRIDKEEP builds systems that solve real business challenges. Every project below reflects its actual, current status."
        model="architecture"
      />

      <section className="border-b border-line bg-black-near py-16 md:py-24" aria-label="All projects">
        <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-5 px-6 sm:grid-cols-2 md:px-10 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.slug} project={project} />
          ))}
        </div>
      </section>

      <ContactPortal />
    </>
  );
}
