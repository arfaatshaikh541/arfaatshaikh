import { SITE_NAME, SITE_URL, SITE_DESCRIPTION, CONTACT_EMAIL, FOUNDER_NAME } from "./constants";

export function organizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE_NAME,
    url: SITE_URL,
    logo: `${SITE_URL}/icons/logo.svg`,
    description: SITE_DESCRIPTION,
    email: CONTACT_EMAIL,
    founder: {
      "@type": "Person",
      name: FOUNDER_NAME,
    },
    address: {
      "@type": "PostalAddress",
      addressCountry: "AE",
    },
  };
}

export function websiteSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: SITE_NAME,
    url: SITE_URL,
    potentialAction: {
      "@type": "SearchAction",
      target: `${SITE_URL}/insights?q={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  };
}

export function breadcrumbSchema(items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: `${SITE_URL}${item.path}`,
    })),
  };
}

export function serviceSchema(args: { name: string; description: string; path: string }) {
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    serviceType: args.name,
    name: args.name,
    description: args.description,
    url: `${SITE_URL}${args.path}`,
    provider: {
      "@type": "Organization",
      name: SITE_NAME,
      url: SITE_URL,
    },
    areaServed: "Global",
  };
}

export function articleSchema(args: {
  title: string;
  description: string;
  path: string;
  datePublished: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: args.title,
    description: args.description,
    url: `${SITE_URL}${args.path}`,
    datePublished: args.datePublished,
    author: {
      "@type": "Organization",
      name: SITE_NAME,
    },
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      logo: {
        "@type": "ImageObject",
        url: `${SITE_URL}/icons/logo.svg`,
      },
    },
  };
}

export function contactPageSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "ContactPage",
    name: `Contact ${SITE_NAME}`,
    url: `${SITE_URL}/contact`,
    about: {
      "@type": "Organization",
      name: SITE_NAME,
      email: CONTACT_EMAIL,
    },
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

export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return {
    __html: JSON.stringify(data),
  };
}
