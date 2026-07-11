import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/constants";
import { services } from "@/data/services";
import { projects } from "@/data/projects";
import { insights } from "@/data/insights";

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

  const now = new Date();

  const entries: MetadataRoute.Sitemap = staticRoutes.map((path) => ({
    url: `${SITE_URL}${path}`,
    lastModified: now,
    changeFrequency: path === "" ? "weekly" : "monthly",
    priority: path === "" ? 1 : 0.7,
  }));

  services.forEach((s) => {
    entries.push({
      url: `${SITE_URL}/services/${s.slug}`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.8,
    });
  });

  projects.forEach((p) => {
    entries.push({
      url: `${SITE_URL}/projects/${p.slug}`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.6,
    });
  });

  insights.forEach((a) => {
    entries.push({
      url: `${SITE_URL}/insights/${a.slug}`,
      lastModified: new Date(a.date),
      changeFrequency: "yearly",
      priority: 0.5,
    });
  });

  return entries;
}
