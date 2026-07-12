export type InsightSlug =
  | "why-systems-before-features"
  | "security-before-scale"
  | "engineering-ai-agents-that-ship";

export type InsightDefinition = {
  slug: InsightSlug;
  title: string;
  excerpt: string;
  datePublished: string;
  readingTime: string;
  body: string[];
};

export const INSIGHTS: InsightDefinition[] = [
  {
    slug: "why-systems-before-features",
    title: "Why Systems Before Features",
    excerpt:
      "Feature velocity feels like progress until the system underneath can't support what you shipped last quarter. A note on why GRIDKEEP designs the system first.",
    datePublished: "2026-02-10",
    readingTime: "6 min read",
    body: [
      "Most software problems that look like feature gaps are actually architecture gaps wearing a feature's clothing. A missing dashboard is usually a missing data model. A slow release cycle is usually a missing service boundary.",
      "Building the system first means defining what owns which data, how services fail, and where the boundaries sit — before a single screen gets designed. It's slower in week one and faster in every week after.",
      "This is why GRIDKEEP engagements start with architecture, not a feature backlog. Features built on an undefined system accumulate cost that compounds quietly until it can't be ignored.",
    ],
  },
  {
    slug: "security-before-scale",
    title: "Security Before Scale",
    excerpt:
      "Bolting on security after a system has scaled is the most expensive way to secure anything. Why access control and data boundaries come first.",
    datePublished: "2026-03-18",
    readingTime: "5 min read",
    body: [
      "Security debt behaves like technical debt with a longer fuse. A system built without defined access boundaries can run for years without incident — until it can't.",
      "Retrofitting authentication, encryption, and monitoring into a system that already has real users and real data is significantly more expensive than designing it in from the start.",
      "GRIDKEEP treats identity, access control, and data boundaries as architecture decisions, not a checklist applied before launch.",
    ],
  },
  {
    slug: "engineering-ai-agents-that-ship",
    title: "Engineering AI Agents That Ship",
    excerpt:
      "Most AI agent projects stall between demo and production. The gap is almost never the model — it's the missing operational discipline around it.",
    datePublished: "2026-05-02",
    readingTime: "7 min read",
    body: [
      "An agent that works in a demo and an agent that works in production are different engineering problems. Production agents need defined action boundaries, monitoring, cost controls, and a clear escalation path when confidence drops.",
      "The model is rarely the bottleneck. The bottleneck is the operational scaffolding around it — the part that doesn't show up in a demo but determines whether the system can be trusted with real decisions.",
      "GRIDKEEP designs agent systems with that scaffolding from day one: defined tool access, human review thresholds, and monitoring that makes failure visible instead of silent.",
    ],
  },
];

export function getInsightBySlug(slug: string): InsightDefinition | undefined {
  return INSIGHTS.find((i) => i.slug === slug);
}
