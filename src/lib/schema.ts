import { siteConfig, absoluteUrl } from "@/lib/seo";
import type { Article, Service, Project, FAQ } from "@/types";

export function personSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Person",
    "@id": `${siteConfig.url}/#person`,
    name: "Arfaat Shaikh",
    jobTitle: "Creative Engineer",
    description: siteConfig.description,
    url: siteConfig.url,
    email: `mailto:${siteConfig.email}`,
    address: {
      "@type": "PostalAddress",
      addressCountry: "AE",
    },
    worksFor: {
      "@type": "Organization",
      name: "GRIDKEEP",
      url: siteConfig.gridkeepUrl,
    },
    alumniOf: {
      "@type": "CollegeOrUniversity",
      name: "Bachelor's degree in Computer Science",
    },
  };
}

export function organizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${siteConfig.gridkeepUrl}/#organization`,
    name: "GRIDKEEP",
    url: siteConfig.gridkeepUrl,
    founder: {
      "@type": "Person",
      name: "Arfaat Shaikh",
    },
    email: siteConfig.email,
    address: {
      "@type": "PostalAddress",
      addressCountry: "AE",
    },
    description:
      "GRIDKEEP is a founder-led technology studio focused on AI, AI agents, automation, custom software, SaaS development, cybersecurity, cloud and DevOps, and immersive web experiences.",
  };
}

export function websiteSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${siteConfig.url}/#website`,
    name: siteConfig.name,
    url: siteConfig.url,
    description: siteConfig.description,
    publisher: {
      "@id": `${siteConfig.url}/#person`,
    },
    inLanguage: "en",
  };
}

export function profilePageSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "ProfilePage",
    "@id": `${siteConfig.url}/about/#profilepage`,
    mainEntity: {
      "@id": `${siteConfig.url}/#person`,
    },
    url: absoluteUrl("/about"),
    name: "About Arfaat Shaikh",
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
      item: absoluteUrl(item.path),
    })),
  };
}

export function serviceSchema(service: Service) {
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    "@id": `${absoluteUrl(`/services/${service.slug}`)}/#service`,
    name: service.name,
    description: service.heroDescription,
    url: absoluteUrl(`/services/${service.slug}`),
    provider: {
      "@id": `${siteConfig.gridkeepUrl}/#organization`,
    },
    areaServed: {
      "@type": "Country",
      name: "United Arab Emirates",
    },
    serviceType: service.name,
  };
}

export function faqSchema(faqs: FAQ[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };
}

export function articleSchema(article: Article) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    "@id": `${absoluteUrl(`/insights/${article.slug}`)}/#article`,
    headline: article.title,
    description: article.description,
    url: absoluteUrl(`/insights/${article.slug}`),
    datePublished: article.publishedAt,
    dateModified: article.modifiedAt,
    author: {
      "@id": `${siteConfig.url}/#person`,
    },
    publisher: {
      "@id": `${siteConfig.gridkeepUrl}/#organization`,
    },
    articleSection: article.category,
    keywords: article.tags.join(", "),
  };
}

export function contactPageSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "ContactPage",
    "@id": `${absoluteUrl("/contact")}/#contactpage`,
    url: absoluteUrl("/contact"),
    name: "Contact Arfaat Shaikh",
    about: {
      "@id": `${siteConfig.url}/#person`,
    },
  };
}

export function creativeWorkSchema(project: Project) {
  return {
    "@context": "https://schema.org",
    "@type": "CreativeWork",
    "@id": `${absoluteUrl(`/projects/${project.slug}`)}/#work`,
    name: project.title,
    description: project.summary,
    url: absoluteUrl(`/projects/${project.slug}`),
    creator: {
      "@id": `${siteConfig.url}/#person`,
    },
    dateCreated: project.year,
    keywords: project.technologies.join(", "),
  };
}
