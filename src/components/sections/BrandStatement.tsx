import { Reveal } from "@/components/ui/Reveal";
import { SectionLabel } from "@/components/ui/SectionLabel";

export function BrandStatement() {
  return (
    <section className="relative flex min-h-[80vh] items-center overflow-hidden bg-graphite py-32" aria-label="Brand statement">
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(255,90,0,0.1), transparent 60%)",
        }}
        aria-hidden="true"
      />
      <div className="relative z-10 mx-auto max-w-4xl px-6 text-center md:px-10">
        <Reveal>
          <SectionLabel label="Brand positioning" />
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-8 text-balance font-display text-3xl leading-snug text-warm md:text-5xl">
            GRIDKEEP is not an agency chasing trends. It is a technology systems company —
            built around infrastructure, intelligence, and operations that hold up under
            real business pressure.
          </p>
        </Reveal>
        <Reveal delay={0.2}>
          <p className="mx-auto mt-8 max-w-2xl text-balance text-muted">
            Every engagement is founder-led, from architecture through delivery, so the
            people accountable for the outcome are the people who built it.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
