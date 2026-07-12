import type { Metadata } from "next";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import JsonLd from "@/components/ui/JsonLd";
import ServicesIndexGrid from "@/components/sections/ServicesIndexGrid";
import { webPageSchema } from "@/lib/schema";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Services",
  description:
    "Seven engineered systems: AI & AI agents, business automation, custom software, cybersecurity, cloud & DevOps, business systems, and web experiences.",
  alternates: { canonical: "/services" },
  openGraph: { url: "/services", title: `Services — ${SITE.name}` },
};

export default function ServicesPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "Services",
          description: metadata.description as string,
          path: "/services",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "Services", path: "/services" }]} />

      <section className="gk-grid-bg border-b border-gk-graphite bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <p className="gk-eyebrow">Capability Grid</p>
          <h1 className="font-display mt-4 max-w-2xl text-4xl font-bold uppercase leading-tight sm:text-5xl">
            Seven systems. <span className="gk-orange-text">One operating standard.</span>
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-gk-grey">
            Every GRIDKEEP engagement is built from the same set of engineered systems — chosen
            and combined based on what your business actually needs, not a fixed package.
          </p>
        </div>
      </section>

      <section className="bg-gk-black px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-[1600px]">
          <ServicesIndexGrid />
        </div>
      </section>
    </>
  );
}
