import type { Metadata } from "next";
import Link from "next/link";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Industries",
  description:
    "GRIDKEEP engineers AI, automation, software, security, cloud, and business systems for financial services, logistics, real estate, healthcare operations, retail, and professional services.",
  alternates: { canonical: "/industries" },
  openGraph: { url: "/industries", title: `Industries — ${SITE.name}` },
};

const INDUSTRIES = [
  {
    name: "Financial Services",
    detail: "Compliance-aware platforms, audit workflows, and secure data handling for financial operations.",
  },
  {
    name: "Logistics & Supply Chain",
    detail: "Automation cells and system integration for tracking, routing, and operational visibility.",
  },
  {
    name: "Real Estate & Construction",
    detail: "Business systems and reporting infrastructure that consolidate project and portfolio data.",
  },
  {
    name: "Healthcare Operations",
    detail: "Secure, access-controlled systems for operational — not clinical — healthcare workflows.",
  },
  {
    name: "Retail & E-commerce",
    detail: "Customer engagement AI, order automation, and infrastructure built for peak demand.",
  },
  {
    name: "Professional Services",
    detail: "Custom software and business systems that replace spreadsheet-based operations.",
  },
  {
    name: "Government & Public Sector",
    detail: "Security-first architecture and infrastructure for public-facing digital services.",
  },
  {
    name: "Manufacturing",
    detail: "Automation and monitoring systems bridging operational technology and business software.",
  },
];

export default function IndustriesPage() {
  return (
    <>
      <JsonLd data={webPageSchema({ name: "Industries", description: metadata.description as string, path: "/industries" })} />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Industries", path: "/industries" }]} />

      <section className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">Industries</p>
          <h1 className="font-display mt-4 max-w-3xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            Systems engineered for <span className="gk-orange-text">how your industry runs.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-gk-grey">
            The underlying architecture standard stays constant. What changes is the compliance,
            data sensitivity, and operational rhythm each industry requires.
          </p>
        </div>
      </section>

      <section className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {INDUSTRIES.map((industry) => (
              <div key={industry.name} className="gk-panel border border-gk-steel p-6">
                <h2 className="font-display text-lg font-semibold text-gk-white">{industry.name}</h2>
                <p className="mt-3 text-sm leading-relaxed text-gk-grey">{industry.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-gk-black px-5 py-24 text-center sm:px-8">
        <h2 className="font-display mx-auto max-w-2xl text-3xl font-bold uppercase sm:text-4xl">
          Don&apos;t see your industry? <span className="gk-orange-text">That&apos;s fine.</span>
        </h2>
        <p className="mx-auto mt-4 max-w-lg text-base text-gk-grey">
          The architecture standard applies regardless of sector. Tell us what you&apos;re
          running.
        </p>
        <div className="mt-8">
          <Link href="/contact" className="gk-btn gk-btn-primary">
            Open a Project Channel
          </Link>
        </div>
      </section>
    </>
  );
}
