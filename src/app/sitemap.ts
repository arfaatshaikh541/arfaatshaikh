import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/seo";
import { services } from "@/data/services";
import { projects } from "@/data/projects";
import { articles } from "@/data/insights";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${siteConfig.url}/`, lastModified: now, changeFrequency: "monthly", priority: 1 },
    { url: `${siteConfig.url}/about`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: `${siteConfig.url}/services`, lastModified: now, changeFrequency: "monthly", priority: 0.9 },
    { url: `${siteConfig.url}/projects`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${siteConfig.url}/gridkeep`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: `${siteConfig.url}/insights`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${siteConfig.url}/tech-stack`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${siteConfig.url}/process`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${siteConfig.url}/contact`, lastModified: now, changeFrequency: "yearly", priority: 0.6 },
    { url: `${siteConfig.url}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
    { url: `${siteConfig.url}/terms`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
  ];

  const serviceRoutes: MetadataRoute.Sitemap = services.map((service) => ({
    url: `${siteConfig.url}/services/${service.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.85,
  }));

  const projectRoutes: MetadataRoute.Sitemap = projects.map((project) => ({
    url: `${siteConfig.url}/projects/${project.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.7,
  }));

  const articleRoutes: MetadataRoute.Sitemap = articles.map((article) => ({
    url: `${siteConfig.url}/insights/${article.slug}`,
    lastModified: new Date(article.modifiedAt),
    changeFrequency: "monthly",
    priority: 0.6,
  }));

  return [...staticRoutes, ...serviceRoutes, ...projectRoutes, ...articleRoutes];
}
