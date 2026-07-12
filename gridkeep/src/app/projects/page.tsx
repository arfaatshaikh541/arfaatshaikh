import type { Metadata } from "next";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import ProjectsSection from "@/components/sections/ProjectsSection";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Projects",
  description: "Selected GRIDKEEP systems in production: RAFANA, the AI Customer Engagement Platform, and the GRIDKEEP Digital Experience.",
  alternates: { canonical: "/projects" },
  openGraph: { url: "/projects", title: `Projects — ${SITE.name}` },
};

export default function ProjectsPage() {
  return (
    <>
      <JsonLd data={webPageSchema({ name: "Projects", description: metadata.description as string, path: "/projects" })} />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Projects", path: "/projects" }]} />
      <ProjectsSection />
    </>
  );
}
