import type { Metadata } from "next";
import Link from "next/link";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import EcosystemSection from "@/components/sections/EcosystemSection";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";
import { SERVICES } from "@/lib/services-data";

export const metadata: Metadata = {
  title: "GRIDKEEP System",
  description:
    "The GRIDKEEP System: one integrated infrastructure connecting AI compute, automation, software, cybersecurity, cloud, business systems, and web experience labs.",
  alternates: { canonical: "/gridkeep-system" },
  openGraph: { url: "/gridkeep-system", title: `GRIDKEEP System — ${SITE.name}` },
};

export default function GridkeepSystemPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({ name: "GRIDKEEP System", description: metadata.description as string, path: "/gridkeep-system" })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "GRIDKEEP System", path: "/gridkeep-system" }]} />

      <section className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">Infrastructure</p>
          <h1 className="font-display mt-4 max-w-3xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            One system. <span className="gk-orange-text">Seven disciplines.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-gk-grey">
            GRIDKEEP doesn&apos;t sell isolated services. AI, automation, software, security,
            cloud, business systems, and web experience work all run through the same
            architecture standard — a control core with defined, monitored connections to every
            module.
          </p>
        </div>
      </section>

      <EcosystemSection />

      <section className="border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">System Modules</p>
          <h2 className="font-display mt-4 max-w-2xl text-3xl font-bold uppercase sm:text-4xl">
            Every discipline, one standard.
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {SERVICES.map((service) => (
              <Link
                key={service.slug}
                href={`/services/${service.slug}`}
                className="gk-panel border border-gk-steel p-5 transition-colors hover:border-gk-orange/60"
              >
                <span className="gk-eyebrow">{service.index}</span>
                <h3 className="font-display mt-2 text-base font-semibold text-gk-white">{service.name}</h3>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
