import type { Metadata } from "next";
import Link from "next/link";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import AboutFounderStage from "@/components/sections/AboutFounderStage";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "About",
  description:
    "GRIDKEEP is a founder-led technology systems company based in the United Arab Emirates, engineering AI, automation, software, security, cloud, and web systems as one operating standard.",
  alternates: { canonical: "/about" },
  openGraph: { url: "/about", title: `About — ${SITE.name}` },
};

const PRINCIPLES = [
  { title: "Systems before features", detail: "Architecture is decided before a single screen is designed." },
  { title: "Security before scale", detail: "Access control and data boundaries are built in, not bolted on." },
  { title: "Business outcomes before technical noise", detail: "Every system is judged by the operational problem it solves." },
];

export default function AboutPage() {
  return (
    <>
      <JsonLd data={webPageSchema({ name: "About", description: metadata.description as string, path: "/about" })} />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "About", path: "/about" }]} />

      <section className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">About GRIDKEEP</p>
          <h1 className="font-display mt-4 max-w-3xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            A founder-led <span className="gk-orange-text">technology systems</span> company.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-gk-grey">{SITE.description}</p>
        </div>
      </section>

      <section className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto grid max-w-[1600px] items-center gap-14 lg:grid-cols-2 lg:gap-20">
          <div>
            <p className="gk-eyebrow">Founder Systems</p>
            <h2 className="font-display mt-4 text-3xl font-bold uppercase sm:text-4xl">{SITE.founder}</h2>
            <p className="font-mono-tech mt-2 text-sm uppercase tracking-[0.14em] text-gk-orange">
              Founder &amp; Systems Architect
            </p>
            <p className="mt-6 max-w-lg text-base leading-relaxed text-gk-grey">
              GRIDKEEP is founder-led by design. Every engagement runs through one architect, so
              technical execution, commercial understanding, and accountability stay connected —
              instead of getting diluted across account managers and hand-offs.
            </p>
            <p className="mt-4 max-w-lg text-base leading-relaxed text-gk-grey">
              Based in the United Arab Emirates, GRIDKEEP works with businesses that need
              engineered systems, not disconnected tools bolted together under a single invoice.
            </p>
            <dl className="mt-9 space-y-5">
              {PRINCIPLES.map((principle) => (
                <div key={principle.title} className="border-l-2 border-gk-orange pl-4">
                  <dt className="font-display text-lg font-semibold text-gk-white">{principle.title}</dt>
                  <dd className="mt-1 text-sm text-gk-grey">{principle.detail}</dd>
                </div>
              ))}
            </dl>
          </div>
          <AboutFounderStage />
        </div>
      </section>

      <section className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">How We Operate</p>
          <h2 className="font-display mt-4 max-w-2xl text-3xl font-bold uppercase sm:text-4xl">
            One architect. One operating standard.
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-3">
            <div className="gk-panel border border-gk-steel p-6">
              <span className="font-display text-3xl font-bold text-gk-steel-light">01</span>
              <h3 className="font-display mt-2 text-lg font-semibold text-gk-white">Direct access</h3>
              <p className="mt-2 text-sm leading-relaxed text-gk-grey">
                You work directly with the person accountable for the system, from scoping through
                delivery.
              </p>
            </div>
            <div className="gk-panel border border-gk-steel p-6">
              <span className="font-display text-3xl font-bold text-gk-steel-light">02</span>
              <h3 className="font-display mt-2 text-lg font-semibold text-gk-white">Engineering-led scope</h3>
              <p className="mt-2 text-sm leading-relaxed text-gk-grey">
                Proposals reflect what the system actually requires — not a sales-driven package.
              </p>
            </div>
            <div className="gk-panel border border-gk-steel p-6">
              <span className="font-display text-3xl font-bold text-gk-steel-light">03</span>
              <h3 className="font-display mt-2 text-lg font-semibold text-gk-white">Built to operate</h3>
              <p className="mt-2 text-sm leading-relaxed text-gk-grey">
                Monitoring, documentation, and handover are part of delivery, not an afterthought.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-gk-black px-5 py-24 text-center sm:px-8">
        <h2 className="font-display mx-auto max-w-2xl text-3xl font-bold uppercase sm:text-4xl">
          Talk to the <span className="gk-orange-text">architect</span> directly.
        </h2>
        <div className="mt-8">
          <Link href="/contact" className="gk-btn gk-btn-primary">
            Open a Project Channel
          </Link>
        </div>
      </section>
    </>
  );
}
