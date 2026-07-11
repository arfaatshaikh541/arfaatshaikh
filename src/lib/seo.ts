import type { Metadata } from "next";
import { SITE_NAME, SITE_URL } from "./constants";

interface BuildMetadataInput {
  title: string;
  description: string;
  path: string;
  image?: string;
  type?: "website" | "article";
  noIndex?: boolean;
}

export function buildMetadata({
  title,
  description,
  path,
  image = "/opengraph-image",
  type = "website",
  noIndex = false,
}: BuildMetadataInput): Metadata {
  const url = `${SITE_URL}${path}`;
  const fullTitle = path === "/" ? title : `${title} | ${SITE_NAME}`;

  return {
    title: fullTitle,
    description,
    alternates: {
      canonical: url,
    },
    robots: noIndex
      ? { index: false, follow: false }
      : { index: true, follow: true },
    openGraph: {
      title: fullTitle,
      description,
      url,
      siteName: SITE_NAME,
      images: [{ url: image, width: 1200, height: 630, alt: fullTitle }],
      locale: "en_US",
      type,
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description,
      images: [image],
    },
  };
}
