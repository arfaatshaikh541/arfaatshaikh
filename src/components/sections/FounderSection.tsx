import Link from "next/link";
import { Reveal } from "@/components/ui/Reveal";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { FOUNDER_NAME, LOCATION } from "@/lib/constants";

export function FounderSection() {
  return (
    <section className="relative border-t border-line bg-black py-32" aria-labelledby="founder-heading">
      <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-12 px-6 md:grid-cols-2 md:px-10">
        <div>
          <Reveal>
            <SectionLabel index="12" label="Founder" />
          </Reveal>
          <Reveal delay={0.08}>
            <h2 id="founder-heading" className="mt-6 text-balance font-display text-4xl text-warm md:text-5xl">
              Built and led by {FOUNDER_NAME}.
            </h2>
          </Reveal>
        </div>
        <div>
          <Reveal delay={0.12}>
            <p className="text-balance text-muted">
              GRIDKEEP is founder-led from {LOCATION}, combining a technical foundation in
              computer science with commercial understanding built through direct customer
              service and sales experience. That combination shapes how every engagement runs
              — technical execution stays tied to a business outcome, not the other way around.
            </p>
          </Reveal>
          <Reveal delay={0.2}>
            <Link
              href="/about"
              className="mt-8 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest2 text-orange hover:text-orange-bright"
            >
              About GRIDKEEP →
            </Link>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
