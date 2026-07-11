import type { Metadata } from "next";
import { SITE_NAME, SITE_URL, SITE_DESCRIPTION } from "./constants";

interface BuildMetadataArgs {
  title: string;
  description?: string;
  path: string;
  noIndex?: boolean;
}

export function buildMetadata({
  title,
  description = SITE_DESCRIPTION,
  path,
  noIndex = false,
}: BuildMetadataArgs): Metadata {
  const url = `${SITE_URL}${path}`;
  const fullTitle = path === "/" ? `${SITE_NAME} — Systems Behind The Business` : `${title} | ${SITE_NAME}`;

  return {
    title: fullTitle,
    description,
    metadataBase: new URL(SITE_URL),
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
      locale: "en_US",
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description,
    },
  };
}
