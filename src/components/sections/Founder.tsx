import SectionLabel from "@/components/ui/SectionLabel";
import { LinkButton } from "@/components/ui/Button";
import { FOUNDER_NAME, FOUNDER_ROLE } from "@/lib/constants";

export default function Founder() {
  return (
    <section className="relative border-t border-line bg-black py-20 md:py-28" aria-labelledby="founder-heading">
      <div className="mx-auto grid max-w-[1440px] grid-cols-1 items-center gap-14 px-6 md:grid-cols-2 md:px-10">
        <div className="relative mx-auto flex aspect-square w-full max-w-[420px] items-center justify-center">
          <div className="absolute inset-0 rounded-full border border-line" aria-hidden="true" />
          <div className="absolute inset-6 animate-pulse-glow rounded-full border border-orange-primary/40" aria-hidden="true" />
          <div className="absolute inset-12 rounded-full border border-orange-burnt/50" aria-hidden="true" />
          <div className="relative flex h-3/5 w-3/5 items-center justify-center overflow-hidden rounded-full bg-gradient-to-b from-black-surface to-black-graphite">
            <svg viewBox="0 0 100 100" className="h-2/3 w-2/3 text-warmwhite/15" fill="currentColor" aria-hidden="true">
              <circle cx="50" cy="35" r="18" />
              <path d="M15 95c0-22 16-38 35-38s35 16 35 38z" />
            </svg>
          </div>
          <span className="absolute bottom-2 left-1/2 w-max -translate-x-1/2 border border-line bg-black-near px-3 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-muted">
            Portrait placeholder — replace with founder photo
          </span>
        </div>

        <div>
          <SectionLabel>About GRIDKEEP</SectionLabel>
          <h2 id="founder-heading" className="gk-heading mt-5 text-3xl text-warmwhite sm:text-4xl">
            FOUNDER LED. SYSTEMS FOCUSED. <span className="text-orange-primary">RESULTS DRIVEN.</span>
          </h2>
          <p className="mt-5 max-w-lg text-sm leading-relaxed text-muted md:text-base">
            GRIDKEEP is a founder-led technology company built around one principle: business-critical systems
            should be engineered with technical depth, commercial understanding, and direct accountability.
          </p>

          <div className="mt-8 border-t border-line pt-6">
            <p className="font-display text-lg uppercase tracking-wide text-warmwhite">{FOUNDER_NAME}</p>
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-orange-primary">{FOUNDER_ROLE}</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <span className="border border-line px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted">
                Computer Science — Technical Foundation
              </span>
              <span className="border border-line px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted">
                Sales &amp; Service — Business Understanding
              </span>
            </div>
          </div>

          <LinkButton href="/about" variant="secondary" className="mt-8">
            More About GRIDKEEP →
          </LinkButton>
        </div>
      </div>
    </section>
  );
}
