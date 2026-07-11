import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/sections/PageHero";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";
import { JsonLd } from "@/components/seo/JsonLd";
import { ChapterScene } from "@/components/three/ChapterScene";
import { Reveal } from "@/components/ui/Reveal";
import { buildMetadata } from "@/lib/seo";
import { webPageSchema } from "@/lib/schema";
import { services } from "@/data/services";

export const metadata: Metadata = buildMetadata({
  title: "The GRIDKEEP System",
  description:
    "The GRIDKEEP System is how every service — AI, automation, software, security, and infrastructure — connects into one engineered architecture.",
  path: "/gridkeep-system",
});

export default function GridkeepSystemPage() {
  return (
    <>
      <JsonLd
        data={webPageSchema({
          name: "The GRIDKEEP System",
          description: "How GRIDKEEP's services connect into one architecture.",
          path: "/gridkeep-system",
        })}
      />
      <Breadcrumbs items={[{ name: "Home", path: "/" }, { name: "GRIDKEEP System", path: "/gridkeep-system" }]} />

      <div className="relative h-[80vh] w-full overflow-hidden">
        <ChapterScene scene="command" interactive className="absolute inset-0" />
        <div className="relative z-10 mx-auto flex h-full max-w-[1600px] flex-col justify-center px-6 md:px-10">
          <Reveal>
            <p className="font-mono text-xs uppercase tracking-widest2 text-orange">The architecture</p>
          </Reveal>
          <Reveal delay={0.08}>
            <h1 className="mt-6 max-w-2xl text-balance font-display text-5xl text-warm md:text-6xl">
              One system. Every discipline.
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-6 max-w-xl text-balance text-muted">
              GRIDKEEP does not treat AI, automation, software, security, and infrastructure
              as separate service lines. They are modules of one connected system, designed
              to reinforce each other.
            </p>
          </Reveal>
        </div>
      </div>

      <section className="mx-auto max-w-[1600px] px-6 py-24 md:px-10">
        <Reveal>
          <h2 className="max-w-2xl font-display text-3xl text-warm">Why systems thinking matters</h2>
          <p className="mt-4 max-w-2xl text-muted">
            A CRM that isn't connected to automation duplicates work. An AI agent without
            security architecture is a liability. A cloud platform without observability
            fails quietly. Every GRIDKEEP engagement is scoped with the rest of the system
            in mind, even when the immediate project is narrow.
          </p>
        </Reveal>

        <div className="mt-16 grid grid-cols-1 gap-px border border-line bg-line md:grid-cols-3">
          {services.map((service, index) => (
            <Link
              key={service.slug}
              href={`/services/${service.slug}`}
              className="group flex flex-col justify-between bg-black p-6 transition-colors hover:bg-surface"
            >
              <div>
                <span className="font-mono text-[10px] uppercase tracking-widest2 text-orange">
                  Module {String(index + 1).padStart(2, "0")}
                </span>
                <h3 className="mt-3 font-display text-xl text-warm group-hover:text-orange-bright">
                  {service.shortName}
                </h3>
              </div>
              <span className="mt-6 font-mono text-xs uppercase tracking-widest2 text-orange">→</span>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
