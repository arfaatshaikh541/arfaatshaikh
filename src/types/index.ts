export type ModelVariant =
  | "reactor"
  | "neural"
  | "automation"
  | "architecture"
  | "vault"
  | "cluster"
  | "cloud"
  | "grid"
  | "ecosystem";

export interface NavChild {
  label: string;
  href: string;
  description: string;
}

export interface NavItem {
  label: string;
  href: string;
  children?: NavChild[];
}

export interface ServiceSummary {
  slug: string;
  index: string;
  title: string;
  shortTitle: string;
  description: string;
  longDescription: string;
  capabilities: string[];
  model: ModelVariant;
}

export interface PrototypeChapter {
  index: string;
  slug: string;
  title: string;
  description: string;
  model: ModelVariant;
  details: string[];
}

export type ProjectStatus = "Client Platform" | "In Development" | "Internal Product";

export interface Project {
  slug: string;
  title: string;
  status: ProjectStatus;
  summary: string;
  description: string;
  model: ModelVariant;
  focus: string[];
}

export interface InsightArticle {
  slug: string;
  title: string;
  category: string;
  summary: string;
  date: string;
  readTime: string;
  body: string[];
}

export interface Industry {
  slug: string;
  title: string;
  description: string;
}

export interface EcosystemNode {
  id: string;
  label: string;
  angle: number;
}

export interface FAQItem {
  question: string;
  answer: string;
}
