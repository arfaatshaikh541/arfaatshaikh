export interface ProcessStep {
  title: string;
  description: string;
}

export const processSteps: ProcessStep[] = [
  {
    title: "Discovery",
    description:
      "A conversation about the actual problem, not the tool you think you need. What's broken, who it affects, and what happens if it stays broken.",
  },
  {
    title: "Scope & architecture",
    description:
      "A written plan before any code — what's being built, what it depends on, and where the edges of the engagement are, so there are no surprises later.",
  },
  {
    title: "Build",
    description:
      "Iterative work with visible progress, not a black box until launch day. Access control, data handling, and structure are part of the build from the start, not bolted on after.",
  },
  {
    title: "Launch & handover",
    description:
      "Deployed, documented, and handed over in a state your team can actually operate — not dependent on me to keep running.",
  },
  {
    title: "Support",
    description:
      "A defined window after launch for fixes and questions as real usage surfaces things a spec never could.",
  },
];
