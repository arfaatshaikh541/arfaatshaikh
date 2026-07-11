import { CONTACT_EMAIL, FOUNDER_NAME, LOCATION, SITE_NAME, SITE_URL } from "./constants";

export function organizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${SITE_URL}/#organization`,
    name: SITE_NAME,
    url: SITE_URL,
    email: CONTACT_EMAIL,
    founder: {
      "@type": "Person",
      name: FOUNDER_NAME,
    },
    address: {
      "@type": "PostalAddress",
      addressCountry: "AE",
      addressRegion: LOCATION,
    },
    description:
      "GRIDKEEP is a founder-led technology systems company designing AI, automation, software, cybersecurity, cloud infrastructure and immersive digital experiences.",
  };
}

export function websiteSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${SITE_URL}/#website`,
    url: SITE_URL,
    name: SITE_NAME,
    publisher: { "@id": `${SITE_URL}/#organization` },
  };
}

export function webPageSchema(input: { name: string; description: string; path: string }) {
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: input.name,
    description: input.description,
    url: `${SITE_URL}${input.path}`,
    isPartOf: { "@id": `${SITE_URL}/#website` },
  };
}

export function breadcrumbSchema(items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: `${SITE_URL}${item.path}`,
    })),
  };
}

export function serviceSchema(input: {
  name: string;
  description: string;
  path: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    serviceType: input.name,
    name: input.name,
    description: input.description,
    url: `${SITE_URL}${input.path}`,
    provider: { "@id": `${SITE_URL}/#organization` },
    areaServed: LOCATION,
  };
}

export function contactPageSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "ContactPage",
    url: `${SITE_URL}/contact`,
    name: `Contact ${SITE_NAME}`,
    about: { "@id": `${SITE_URL}/#organization` },
  };
}

export function articleSchema(input: {
  title: string;
  description: string;
  slug: string;
  publishedAt: string;
  modifiedAt: string;
  author: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: input.title,
    description: input.description,
    url: `${SITE_URL}/insights/${input.slug}`,
    datePublished: input.publishedAt,
    dateModified: input.modifiedAt,
    author: { "@type": "Person", name: input.author },
    publisher: { "@id": `${SITE_URL}/#organization` },
    mainEntityOfPage: `${SITE_URL}/insights/${input.slug}`,
  };
}

export function creativeWorkSchema(input: {
  name: string;
  description: string;
  slug: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "CreativeWork",
    name: input.name,
    description: input.description,
    url: `${SITE_URL}/projects/${input.slug}`,
    creator: { "@id": `${SITE_URL}/#organization` },
  };
}

export function softwareApplicationSchema(input: {
  name: string;
  description: string;
  slug: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: input.name,
    description: input.description,
    url: `${SITE_URL}/projects/${input.slug}`,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
  };
}

export function faqSchema(items: { question: string; answer: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}
