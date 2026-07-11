export type SceneId =
  | "core"
  | "neural"
  | "assembly"
  | "architecture"
  | "vault"
  | "orbit"
  | "weblab"
  | "network"
  | "command"
  | "portal";

export interface Service {
  slug: string;
  name: string;
  shortName: string;
  eyebrow: string;
  summary: string;
  description: string;
  capabilities: string[];
  scene: SceneId;
  relatedIndustries: string[];
  faqs?: { question: string; answer: string }[];
}

export type ProjectStatus = "Client Platform" | "In Development" | "Internal Product";

export interface Project {
  slug: string;
  name: string;
  status: ProjectStatus;
  summary: string;
  description: string;
  technologies: string[];
  relatedServices: string[];
  scene: SceneId;
}

export interface Industry {
  slug: string;
  name: string;
  description: string;
  relevantServices: string[];
}

export interface InsightMeta {
  slug: string;
  title: string;
  description: string;
  category: string;
  author: string;
  publishedAt: string;
  modifiedAt: string;
  readingTime: string;
}

export interface Insight extends InsightMeta {
  contentHtml: string;
  headings: { id: string; text: string; depth: number }[];
}
