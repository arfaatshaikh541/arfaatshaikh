import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/constants";
import { services } from "@/data/services";
import { projects } from "@/data/projects";
import { getAllInsightsMeta } from "@/lib/insights";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticRoutes = [
    "",
    "/about",
    "/services",
    "/projects",
    "/industries",
    "/gridkeep-system",
    "/insights",
    "/contact",
    "/privacy",
    "/terms",
  ];

  const serviceRoutes = services.map((service) => `/services/${service.slug}`);
  const projectRoutes = projects.map((project) => `/projects/${project.slug}`);
  const insightRoutes = getAllInsightsMeta().map((insight) => `/insights/${insight.slug}`);

  const allRoutes = [...staticRoutes, ...serviceRoutes, ...projectRoutes, ...insightRoutes];

  return allRoutes.map((route) => ({
    url: `${SITE_URL}${route}`,
    lastModified: new Date(),
    changeFrequency: route === "" ? "weekly" : "monthly",
    priority: route === "" ? 1 : 0.7,
  }));
}
