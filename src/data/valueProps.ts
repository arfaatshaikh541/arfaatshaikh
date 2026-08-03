export interface ValueProp {
  label: string;
  caption: string;
}

// Deliberately qualitative, not numeric — no invented years-of-experience,
// project counts, client counts, or "countries served" figures.
export const valueProps: ValueProp[] = [
  { label: "Full-Stack", caption: "Concept to production" },
  { label: "AI-Native", caption: "Agents, not just chatbots" },
  { label: "Security by Design", caption: "Not an afterthought" },
  { label: "Remote-First", caption: "Works with teams anywhere" },
];
