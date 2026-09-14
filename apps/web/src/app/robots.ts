import type { MetadataRoute } from "next";

// The application (app.arfaat.com/worldofislam) is authenticated and must
// never be crawled or indexed. The public, indexable overview page is a
// separate deployment at arfaat.com/worldofislam with its own robots policy.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", disallow: "/" },
  };
}
