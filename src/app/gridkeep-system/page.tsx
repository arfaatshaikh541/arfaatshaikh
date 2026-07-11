import { buildMetadata } from "@/lib/seo";
import { breadcrumbSchema, faqSchema } from "@/lib/schema";
import JsonLd from "@/components/ui/JsonLd";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import SectionLabel from "@/components/ui/SectionLabel";
import PrototypeCard from "@/components/ui/PrototypeCard";
import Ecosystem from "@/components/sections/Ecosystem";
import ContactPortal from "@/components/sections/ContactPortal";
import { prototypeChapters } from "@/data/prototypes";

const faqs = [
  {
    question: "What is the GRIDKEEP System?",
    answer:
      "The GRIDKEEP System is how we describe the connected set of engineering disciplines — AI, automation, software, cybersecurity, cloud infrastructure and business systems — that GRIDKEEP builds as one coherent operating layer for a business, rather than as separate, disconnected tools.",
  },
  {
    question: "Do I need every part of the system, or can I start with one piece?",
    answer:
      "Most engagements start with a single system — often automation or a custom software platform — and expand as the underlying architecture proves itself. The system is designed to connect incrementally, not to require an all-or-nothing rebuild.",
  },
  {
    question: "Who architects these systems?",
    answer:
      "GRIDKEEP is founder-led. Arfaat Shaikh, Founder & Systems Architect, is directly involved in the technical architecture of every engagement.",
  },
];

export const metadata = buildMetadata({
  title: "The GRIDKEEP System",
  description:
    "Explore the GRIDKEEP System — the engineering chapters and connected ecosystem behind every AI, automation, software, cybersecurity and cloud system GRIDKEEP builds.",
  path: "/gridkeep-system",
});

const crumbs = [
  { name: "Home", path: "/" },
  { name: "GRIDKEEP System", path: "/gridkeep-system" },
];

export default function GridkeepSystemPage() {
  return (
    <>
      <JsonLd data={breadcrumbSchema(crumbs)} />
      <JsonLd data={faqSchema(faqs)} />
      <Breadcrumbs items={crumbs} />

      <section className="relative overflow-hidden border-b border-line bg-black py-16 md:py-24">
        <div className="pointer-events-none absolute inset-0 bg-grid-lines bg-[size:52px_52px] opacity-[0.25]" aria-hidden="true" />
        <div className="relative mx-auto max-w-[1440px] px-6 md:px-10">
          <p className="gk-eyebrow mb-5">The GRIDKEEP System</p>
          <h1 className="gk-heading max-w-3xl text-4xl text-warmwhite sm:text-5xl md:text-6xl">
            ONE ARCHITECTURE. <span className="text-orange-primary">FIVE ENGINEERING CHAPTERS.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-sm leading-relaxed text-muted md:text-base">
            Every GRIDKEEP engagement draws from the same underlying system — five engineering chapters that connect
            into one ecosystem, from the central core to AI, automation, software architecture and cybersecurity.
          </p>
        </div>
      </section>

      <section className="border-b border-line bg-black-near py-16 md:py-24">
        <div className="mx-auto max-w-[1440px] px-6 md:px-10">
          <SectionLabel index="CH. 01 — 05">Engineering Chapters</SectionLabel>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {prototypeChapters.map((chapter) => (
              <div key={chapter.slug} id={chapter.slug} className="scroll-mt-24">
                <PrototypeCard chapter={chapter} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <Ecosystem />

      <section className="border-b border-line bg-black py-16 md:py-24">
        <div className="mx-auto max-w-[1440px] px-6 md:px-10">
          <SectionLabel>Frequently Asked</SectionLabel>
          <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
            {faqs.map((faq) => (
              <div key={faq.question} className="gk-card p-6">
                <h2 className="font-display text-base uppercase tracking-wide text-warmwhite">{faq.question}</h2>
                <p className="mt-3 text-sm leading-relaxed text-muted">{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <ContactPortal />
    </>
  );
}
