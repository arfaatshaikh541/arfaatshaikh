export type ServiceCategory =
  | "ai-automation"
  | "software-saas"
  | "cybersecurity"
  | "cloud-devops"
  | "web-experiences";

export interface ProcessStep {
  step: string;
  title: string;
  description: string;
}

export interface FAQ {
  question: string;
  answer: string;
}

export interface ServicePillar {
  slug: string;
  name: string;
  tagline: string;
  summary: string;
}

export interface Service {
  slug: ServiceCategory;
  name: string;
  shortName: string;
  tagline: string;
  heroDescription: string;
  overview: string[];
  problems: string[];
  capabilities: { title: string; description: string }[];
  process: ProcessStep[];
  technologies: string[];
  useCases: string[];
  faqs: FAQ[];
  pillars: ServicePillar[];
  relatedSlugs: ServiceCategory[];
}

export type ProjectStatus =
  | "Concept"
  | "In Development"
  | "Internal Product"
  | "Client Platform";

export interface Project {
  slug: string;
  title: string;
  category: string;
  status: ProjectStatus;
  year: string;
  summary: string;
  description: string[];
  role: string;
  industry: string;
  capabilities: string[];
  technologies: string[];
  highlights: string[];
  image: string;
}

export interface ArticleSection {
  id: string;
  heading: string;
  paragraphs: string[];
  list?: string[];
}

export interface Article {
  slug: string;
  title: string;
  description: string;
  category: string;
  excerpt: string;
  publishedAt: string;
  modifiedAt: string;
  author: string;
  tags: string[];
  sections: ArticleSection[];
  faqs?: FAQ[];
  relatedSlugs: string[];
}
