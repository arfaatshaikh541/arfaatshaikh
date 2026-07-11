import type { Metadata } from "next";

export const siteConfig = {
  name: "Arfaat Shaikh",
  title: "Arfaat Shaikh — Creative Engineer & Founder of GRIDKEEP",
  description:
    "Arfaat Shaikh is a creative engineer based in the United Arab Emirates and founder of GRIDKEEP, building AI agents, automation, custom software, cybersecurity, cloud infrastructure, and immersive web experiences.",
  url: "https://arfaat.com",
  email: "hello@arfaat.com",
  gridkeepUrl: "https://gridkeep.com",
  locale: "en_US",
  themeColor: "#000000",
};

export function absoluteUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${siteConfig.url}${normalized === "/" ? "" : normalized}`;
}

interface BuildMetadataOptions {
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
  image,
  type = "website",
  noIndex = false,
}: BuildMetadataOptions): Metadata {
  const url = absoluteUrl(path);
  // When no explicit image is given, omit `images` entirely so Next.js falls
  // back to the file-convention opengraph-image.tsx (see src/app/) instead
  // of pointing at a hardcoded path that may not exist for every route.
  const imageUrl = image ? (image.startsWith("http") ? image : absoluteUrl(image)) : undefined;

  return {
    title,
    description,
    alternates: {
      canonical: url,
    },
    robots: noIndex
      ? { index: false, follow: false }
      : { index: true, follow: true },
    openGraph: {
      title,
      description,
      url,
      siteName: siteConfig.name,
      type,
      locale: siteConfig.locale,
      ...(imageUrl
        ? { images: [{ url: imageUrl, width: 1200, height: 630, alt: title }] }
        : {}),
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      ...(imageUrl ? { images: [imageUrl] } : {}),
    },
  };
}
