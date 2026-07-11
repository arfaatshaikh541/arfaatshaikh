import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import SectionLabel from "@/components/ui/SectionLabel";
import Founder from "@/components/sections/Founder";
import ContactPortal from "@/components/sections/ContactPortal";
import { FOUNDER_NAME, LOCATION } from "@/lib/constants";

export const metadata = buildMetadata({
  title: "About GRIDKEEP",
  description:
    "GRIDKEEP is a founder-led technology systems company based in the United Arab Emirates, engineering AI, automation, software, cybersecurity and cloud infrastructure.",
  path: "/about",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "About", path: "/about" },
];

const principles = [
  {
    title: "Founder Led",
    description: "Direct accountability. The founder is the systems architect on every engagement, not a layer removed from it.",
  },
  {
    title: "Systems Thinking",
    description: "We engineer the connective layer between tools, not just another isolated tool.",
  },
  {
    title: "Secure & Reliable",
    description: "Security and reliability are built in from the architecture stage, not added afterward.",
  },
  {
    title: "Scalable Solutions",
    description: "Systems are built to grow with the business, not to be rebuilt at the next stage.",
  },
];

export default function AboutPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <Breadcrumbs items={crumbs} />

      <section className="relative overflow-hidden border-b border-line bg-black py-16 md:py-24">
        <div className="pointer-events-none absolute inset-0 bg-grid-lines bg-[size:52px_52px] opacity-[0.25]" aria-hidden="true" />
        <div className="relative mx-auto max-w-[1440px] px-6 md:px-10">
          <p className="gk-eyebrow mb-5">About GRIDKEEP</p>
          <h1 className="gk-heading max-w-3xl text-4xl text-warmwhite sm:text-5xl md:text-6xl">
            TECHNOLOGY, ENGINEERED <span className="text-orange-primary">WITH ACCOUNTABILITY.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-sm leading-relaxed text-muted md:text-base">
            GRIDKEEP is a technology company founded by {FOUNDER_NAME} in {LOCATION}. We combine technical foundation
            in Computer Science with real-world experience in customer service and sales to connect technology
            decisions with business outcomes.
          </p>
        </div>
      </section>

      <section className="border-b border-line bg-black-near py-16 md:py-24">
        <div className="mx-auto max-w-[1440px] px-6 md:px-10">
          <SectionLabel>How We Work</SectionLabel>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {principles.map((p) => (
              <div key={p.title} className="gk-card p-6">
                <h2 className="font-display text-base uppercase tracking-wide text-warmwhite">{p.title}</h2>
                <p className="mt-3 text-sm leading-relaxed text-muted">{p.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Founder />
      <ContactPortal />
    </>
  );
}
