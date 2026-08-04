import type { Article } from "@/types";

export const articles: Article[] = [
  {
    slug: "ai-agents-automate-customer-service",
    title: "How AI Agents Can Automate Customer Service",
    description:
      "A practical look at how AI agents handle real customer service work — what they can take on today, what still needs a human, and how to introduce them without losing quality.",
    category: "AI & Automation",
    excerpt:
      "AI agents are now capable of handling a meaningful share of customer service work — not by replacing your team, but by absorbing the repetitive, time-sensitive load that currently falls through the cracks.",
    publishedAt: "2025-02-11",
    modifiedAt: "2025-02-11",
    author: "Arfaat Shaikh",
    tags: ["AI Agents", "Customer Service", "Automation"],
    sections: [
      {
        id: "the-real-problem",
        heading: "The real problem isn't volume, it's timing",
        paragraphs: [
          "Most businesses do not struggle with customer service because they receive too many enquiries. They struggle because enquiries arrive at inconvenient times — after hours, over weekends, during a rush — and the gap between question and answer is where customers are lost.",
          "A generic FAQ chatbot does not solve this because it cannot act. It can recite information, but it cannot check availability, qualify a lead, or update a record. The value of an AI agent comes from connecting understanding to action.",
        ],
      },
      {
        id: "what-agents-can-actually-do",
        heading: "What AI agents can actually do today",
        paragraphs: [
          "A well-scoped AI agent can hold a natural conversation about your specific services, answer questions using your actual pricing and policies, qualify a lead by asking the right follow-up questions, check availability against a real calendar, and hand off to a human the moment a conversation needs judgement a machine shouldn't make.",
        ],
        list: [
          "Answering service and pricing questions using your real business data",
          "Qualifying leads before they reach your sales team",
          "Booking or rescheduling appointments against live availability",
          "Following up automatically when a conversation goes quiet",
          "Escalating clearly to a human when the conversation requires it",
        ],
      },
      {
        id: "where-a-human-is-still-required",
        heading: "Where a human is still required",
        paragraphs: [
          "Complaints, refunds, anything emotionally charged, and any decision with real financial or legal consequence should still route to a person. A good agent is designed to recognise these situations and hand off cleanly, rather than attempt to resolve everything itself.",
          "The goal is not full automation. It is removing the repetitive, low-judgement work so your team's time goes toward the conversations that actually need them.",
        ],
      },
      {
        id: "introducing-an-agent-without-losing-quality",
        heading: "Introducing an agent without losing quality",
        paragraphs: [
          "The businesses that get the most value start narrow: one channel, one clearly defined set of questions, with visibility into every conversation the agent handles. Scope expands once the agent has proven itself against real traffic, not assumptions.",
          "Logging and review matter as much as the agent itself. If you cannot see what the agent said and why, you cannot trust it with more responsibility over time.",
        ],
      },
    ],
    faqs: [
      {
        question: "Will customers know they're talking to an AI agent?",
        answer:
          "Best practice is to be transparent about it. Customers generally accept AI-assisted service well when it is fast, accurate, and clearly able to reach a human when needed.",
      },
      {
        question: "How long does it take to set up an AI customer service agent?",
        answer:
          "It depends on scope — a single, well-defined use case can be built and tested faster than a system spanning multiple departments and tools. Scope is assessed honestly per business.",
      },
    ],
    relatedSlugs: [
      "ai-automation-for-uae-businesses",
      "why-businesses-need-crm-erp-integration",
    ],
  },
  {
    slug: "ai-automation-for-uae-businesses",
    title: "AI Automation for UAE Businesses",
    description:
      "Why UAE businesses across services, real estate, and retail are strong candidates for AI automation, and how to approach adopting it practically.",
    category: "AI & Automation",
    excerpt:
      "The UAE's fast-moving, service-driven business environment creates unusually strong conditions for AI automation to pay off quickly — if it's implemented around the right processes.",
    publishedAt: "2025-03-04",
    modifiedAt: "2025-03-04",
    author: "Arfaat Shaikh",
    tags: ["AI Automation", "UAE Business", "Digital Strategy"],
    sections: [
      {
        id: "why-the-uae-market-fits",
        heading: "Why the UAE market fits AI automation well",
        paragraphs: [
          "The UAE has a dense, competitive services economy — real estate, hospitality, clinics, salons, retail — where response speed directly affects revenue. Customers compare multiple providers quickly, often over WhatsApp, and the business that responds first frequently wins the enquiry.",
          "This makes automation less of a nice-to-have and more of a competitive requirement: businesses that respond instantly and consistently outperform those relying on manual follow-up, regardless of the underlying quality of their service.",
        ],
      },
      {
        id: "common-starting-points",
        heading: "Common starting points for UAE businesses",
        paragraphs: [
          "The businesses that see the fastest return typically start with one of a few well-understood use cases rather than attempting to automate everything at once.",
        ],
        list: [
          "Instant WhatsApp response and lead qualification for real estate and services",
          "Appointment booking automation for clinics, salons, and gyms",
          "Automated follow-up sequences for leads that go quiet",
          "Document and invoice processing for accounting and advisory firms",
        ],
      },
      {
        id: "language-and-context",
        heading: "Language, tone, and local context matter",
        paragraphs: [
          "A generic, US-trained chatbot script tends to feel noticeably out of place in the UAE market. Automation that performs well here is built around the way local customers actually communicate — including bilingual conversation handling where relevant — and around real business hours, holidays, and expectations.",
        ],
      },
      {
        id: "getting-started-practically",
        heading: "Getting started practically",
        paragraphs: [
          "The most reliable path is to automate one clear workflow completely — for example, WhatsApp lead response — before expanding into other departments. Trying to automate everything simultaneously tends to produce a system nobody fully trusts.",
        ],
      },
    ],
    faqs: [
      {
        question: "Is AI automation only useful for large companies in the UAE?",
        answer:
          "No — smaller and mid-sized service businesses often see the fastest, most visible impact, since a single missed enquiry represents a larger share of their potential revenue.",
      },
      {
        question: "Does automation work well with WhatsApp in the UAE?",
        answer:
          "Yes. WhatsApp is a primary communication channel for UAE consumers, and the WhatsApp Business API supports the kind of automated, agent-assisted conversations described here.",
      },
    ],
    relatedSlugs: [
      "ai-agents-automate-customer-service",
      "how-immersive-websites-improve-brand-experience",
    ],
  },
  {
    slug: "custom-software-vs-off-the-shelf-software",
    title: "Custom Software vs Off-the-Shelf Software",
    description:
      "An honest breakdown of when off-the-shelf software is the right call, and when the constraints of generic tools start costing more than a custom build.",
    category: "Software Development",
    excerpt:
      "Off-the-shelf software is right more often than developers like to admit. The decision comes down to how well your process fits the average case the tool was built for.",
    publishedAt: "2025-04-18",
    modifiedAt: "2025-04-18",
    author: "Arfaat Shaikh",
    tags: ["Custom Software", "SaaS", "Business Systems"],
    sections: [
      {
        id: "the-honest-starting-point",
        heading: "The honest starting point",
        paragraphs: [
          "Off-the-shelf software exists because most businesses run reasonably standard processes, and paying to rebuild something that already works well is a poor use of money. If a tool like a standard CRM, accounting platform, or booking system covers 90% of what you need, custom software is usually the wrong answer.",
          "Custom software earns its cost when the remaining 10% — the exceptions, the specific workflow, the way departments actually hand work to each other — is where the real value of the business lives.",
        ],
      },
      {
        id: "signs-off-the-shelf-is-still-right",
        heading: "Signs off-the-shelf software is still the right call",
        paragraphs: [
          "If your process is close to how most businesses in your category operate, a mature off-the-shelf tool will almost always be faster to launch and cheaper to maintain than a custom build.",
        ],
        list: [
          "Your workflow closely matches how most businesses in your industry operate",
          "The available tools already integrate well with each other",
          "You need to move fast and validate an idea before investing further",
          "Ongoing maintenance and updates being handled by a vendor is a real advantage for you",
        ],
      },
      {
        id: "signs-custom-makes-sense",
        heading: "Signs custom software makes sense",
        paragraphs: [
          "Custom software becomes the stronger option once workarounds start costing more — in time, errors, or lost opportunities — than building the right tool would.",
        ],
        list: [
          "Staff maintain manual workarounds or spreadsheets because no tool fits the process",
          "You need multi-tenant architecture to serve your own clients as a platform",
          "Data lives in disconnected systems with no reliable way to unify it",
          "The workflow itself is a competitive advantage worth protecting and owning",
        ],
      },
      {
        id: "the-middle-ground",
        heading: "The middle ground: integration over rebuilding",
        paragraphs: [
          "In many cases, the right answer is neither pure off-the-shelf nor a full custom rebuild — it's integrating your existing tools properly so data moves between them without manual re-entry. This captures most of the benefit of a custom system at a fraction of the cost.",
        ],
      },
    ],
    faqs: [
      {
        question: "Is custom software always more expensive?",
        answer:
          "Upfront, usually yes. Over time, if off-the-shelf tools force expensive workarounds or fail to scale with your business, custom software can be the more cost-effective option in total.",
      },
      {
        question: "Can custom software integrate with our existing off-the-shelf tools?",
        answer:
          "Yes — a common and often ideal pattern is custom software built specifically to fill the gap, integrated with the off-the-shelf tools that already work well for you.",
      },
    ],
    relatedSlugs: [
      "why-businesses-need-crm-erp-integration",
      "ai-agents-automate-customer-service",
    ],
  },
  {
    slug: "cybersecurity-fundamentals-for-small-businesses",
    title: "Cybersecurity Fundamentals for Small Businesses",
    description:
      "The cybersecurity fundamentals that matter most for small and growing businesses, without the noise of enterprise security marketing.",
    category: "Cybersecurity",
    excerpt:
      "Small businesses are frequently the least protected, not because security is complicated, but because the fundamentals get skipped under time pressure.",
    publishedAt: "2025-05-09",
    modifiedAt: "2025-05-09",
    author: "Arfaat Shaikh",
    tags: ["Cybersecurity", "Small Business", "Risk Management"],
    sections: [
      {
        id: "why-small-businesses-are-targets",
        heading: "Why small businesses are targets, not just enterprises",
        paragraphs: [
          "Small and mid-sized businesses are frequently targeted precisely because they tend to have weaker defences than large enterprises while still holding valuable customer and payment data. Attackers often prefer easier targets over harder, better-defended ones.",
        ],
      },
      {
        id: "the-fundamentals-that-matter",
        heading: "The fundamentals that actually matter",
        paragraphs: [
          "Most breaches do not involve sophisticated attacks. They involve basic gaps: weak or reused passwords, no multi-factor authentication, overly broad access permissions, and unpatched software. Fixing these fundamentals removes the majority of real-world risk before anything more advanced is needed.",
        ],
        list: [
          "Multi-factor authentication on every account that supports it",
          "Least-privilege access — staff only have access to what their role requires",
          "Regular software and dependency updates",
          "Encrypted storage and transmission of customer data",
          "A basic incident response plan, even a simple one, written down before it's needed",
        ],
      },
      {
        id: "common-mistakes",
        heading: "Common mistakes in growing businesses",
        paragraphs: [
          "As businesses grow quickly, access control is usually the first thing to slip — new staff get broad permissions for convenience, and nobody revokes access when people change roles or leave. This is one of the most common sources of real exposure.",
          "APIs and third-party integrations are another common weak point: connections get added quickly to ship a feature, without proper authentication or rate limiting, and are rarely revisited.",
        ],
      },
      {
        id: "a-practical-starting-point",
        heading: "A practical starting point",
        paragraphs: [
          "Start with an honest assessment of what data and systems you actually have exposed, rank the findings by real business impact, and fix the highest-impact issues first. Security does not need to be perfect to meaningfully reduce risk — it needs to be prioritised correctly.",
        ],
      },
    ],
    faqs: [
      {
        question: "Do we need a dedicated security team?",
        answer:
          "Not necessarily at a small scale. Many of the highest-impact fixes are architectural and configuration-based, and can be implemented as part of building or reviewing your systems rather than requiring a standing security team.",
      },
      {
        question: "What's the first thing we should check?",
        answer:
          "Access control. Review who has access to what across your systems, remove anything unnecessary, and enable multi-factor authentication everywhere it's supported.",
      },
    ],
    relatedSlugs: [
      "why-businesses-need-crm-erp-integration",
      "custom-software-vs-off-the-shelf-software",
    ],
  },
  {
    slug: "why-businesses-need-crm-erp-integration",
    title: "Why Businesses Need CRM and ERP Integration",
    description:
      "What happens when CRM and ERP systems don't talk to each other, and why integrating them properly is one of the highest-leverage fixes available to a growing business.",
    category: "Business Systems",
    excerpt:
      "Disconnected CRM and ERP systems quietly cost businesses far more than the software itself — in duplicated work, inconsistent data, and decisions made on incomplete information.",
    publishedAt: "2025-06-02",
    modifiedAt: "2025-06-02",
    author: "Arfaat Shaikh",
    tags: ["CRM", "ERP", "Business Systems", "API Integrations"],
    sections: [
      {
        id: "the-cost-of-disconnected-systems",
        heading: "The hidden cost of disconnected systems",
        paragraphs: [
          "When a CRM and an ERP system don't talk to each other, someone has to. That usually means staff manually re-entering customer, order, or invoice data between systems — a slow, error-prone process that scales badly as the business grows.",
          "The deeper cost is decision-making quality. Sales sees pipeline data without operational context; finance sees invoices without the customer relationship behind them. Nobody has the full picture without pulling reports manually from multiple places.",
        ],
      },
      {
        id: "what-integration-actually-solves",
        heading: "What proper integration actually solves",
        paragraphs: [
          "Integrating CRM and ERP systems means a customer record, order, or invoice created in one system is automatically reflected in the other — no duplicate entry, no drift between what sales and finance believe is true.",
        ],
        list: [
          "Eliminates duplicate manual data entry between systems",
          "Keeps customer, order, and financial data consistent across departments",
          "Gives leadership a single, reliable view of the business",
          "Reduces errors that come from manually copying data between platforms",
        ],
      },
      {
        id: "how-integration-is-usually-approached",
        heading: "How integration is usually approached",
        paragraphs: [
          "Most modern CRM and ERP platforms expose APIs, which makes it possible to build a reliable integration layer between them without replacing either system. This is typically the fastest and lowest-risk path — you keep the tools your team already knows, and remove the manual bridge between them.",
          "Where existing tools don't fit the process well enough, a custom CRM or ERP component can be built specifically to cover the gap, integrated with the systems that already work.",
        ],
      },
      {
        id: "when-to-prioritise-this",
        heading: "When to prioritise this",
        paragraphs: [
          "If your team routinely re-types the same information into two systems, or if sales and finance regularly disagree about numbers, integration is very likely one of the highest-return fixes available — often ahead of any new feature or tool purchase.",
        ],
      },
    ],
    faqs: [
      {
        question: "Do we need to replace our CRM or ERP to integrate them?",
        answer:
          "Usually not. Integration typically works through the APIs the existing tools already expose, connecting them without requiring either system to be replaced.",
      },
      {
        question: "How long does a CRM/ERP integration take?",
        answer:
          "It depends on the complexity of the data being synced and how many systems are involved. A single, well-defined integration is significantly faster than a multi-system overhaul.",
      },
    ],
    relatedSlugs: [
      "custom-software-vs-off-the-shelf-software",
      "ai-automation-for-uae-businesses",
    ],
  },
  {
    slug: "how-immersive-websites-improve-brand-experience",
    title: "How Immersive Websites Improve Brand Experience",
    description:
      "Why well-executed immersive and 3D web experiences change how a brand is perceived, and how to build them without sacrificing performance or accessibility.",
    category: "Web Experiences",
    excerpt:
      "An immersive website isn't decoration — done properly, it signals technical seriousness before a single word of copy is read.",
    publishedAt: "2025-06-27",
    modifiedAt: "2025-06-27",
    author: "Arfaat Shaikh",
    tags: ["Web Design", "WebGL", "Brand Experience"],
    sections: [
      {
        id: "why-first-impressions-are-technical",
        heading: "Why first impressions are technical, not just visual",
        paragraphs: [
          "Before a visitor reads a single sentence, the way a site loads, moves, and responds has already communicated something about the business behind it. A generic template signals a generic business, regardless of how strong the underlying work actually is.",
          "A well-built immersive experience — smooth motion, considered pacing, a distinct visual identity — signals technical seriousness immediately, which matters most for businesses selling technical capability in the first place.",
        ],
      },
      {
        id: "what-immersive-actually-means",
        heading: "What 'immersive' actually means done well",
        paragraphs: [
          "Immersive does not mean maximalist. The strongest 3D and motion-driven sites use restraint — a signature visual element, scroll-driven pacing, and purposeful transitions — rather than piling on effects for their own sake. Overuse of motion and glow reads as amateur, not premium.",
        ],
      },
      {
        id: "the-performance-and-accessibility-trap",
        heading: "The performance and accessibility trap",
        paragraphs: [
          "The most common failure mode for immersive sites is treating performance and accessibility as an afterthought. A beautiful 3D scene that takes eight seconds to load, or that renders no readable content without WebGL, actively damages both user experience and search visibility.",
          "Done correctly, real content is server-rendered as accessible HTML alongside the 3D layer, quality is adapted to device capability, and a static fallback is shown immediately while heavier assets load in the background — so the experience degrades gracefully rather than breaking.",
        ],
      },
      {
        id: "when-immersive-is-and-isnt-the-right-call",
        heading: "When immersive is — and isn't — the right call",
        paragraphs: [
          "Immersive, motion-driven experiences make the most sense for flagship brand sites, product showcases, and portfolios where the site itself is part of the pitch. They make less sense for high-frequency transactional tools, where speed and simplicity outrank spectacle.",
        ],
      },
    ],
    faqs: [
      {
        question: "Do immersive websites hurt page load speed?",
        answer:
          "They can, if built carelessly. Built correctly — with lazy-loaded 3D assets, capped device pixel ratios, adaptive particle counts, and a fast-loading static fallback — an immersive site can still meet strong Core Web Vitals targets.",
      },
      {
        question: "Are 3D websites accessible?",
        answer:
          "They can and should be. Real navigation, real text content, keyboard access, and reduced-motion support should all exist independently of the 3D layer, which is treated as an enhancement rather than a requirement to use the site.",
      },
    ],
    relatedSlugs: [
      "ai-automation-for-uae-businesses",
      "ai-agents-automate-customer-service",
    ],
  },
];

export function getArticleBySlug(slug: string): Article | undefined {
  return articles.find((article) => article.slug === slug);
}

export function getReadingTime(article: Article): number {
  const words = article.sections
    .flatMap((section) => [section.heading, ...section.paragraphs, ...(section.list ?? [])])
    .join(" ")
    .trim()
    .split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}
