import Link from "next/link";

export function GridkeepSection() {
  return (
    <section
      className="border-b border-[var(--color-line)] bg-[var(--color-surface)] py-24 md:py-32"
      aria-labelledby="gridkeep-heading"
    >
      <div className="container-edge">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Founder-Led Technology Studio
        </p>
        <h2 id="gridkeep-heading" className="mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] md:text-6xl">
          GRIDKEEP
        </h2>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          GRIDKEEP is the studio behind this work — a founder-led technology
          practice spanning AI, AI agents, automation, custom software,
          cybersecurity, cloud infrastructure, and immersive web experiences.
          It exists to give businesses one accountable partner for the
          systems they depend on, instead of piecing it together across
          disconnected vendors.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <Link
            href="/gridkeep"
            className="inline-flex items-center gap-3 border border-[var(--color-blood-red)] bg-[var(--color-blood-red)] px-6 py-3 font-mono text-xs uppercase tracking-[0.15em] text-black transition-colors hover:bg-transparent hover:text-[var(--color-blood-red)]"
          >
            Enter GRIDKEEP →
          </Link>
          <a
            href="https://gridkeep.com"
            className="inline-flex items-center gap-3 border border-[var(--color-line)] px-6 py-3 font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
          >
            gridkeep.com ↗
          </a>
        </div>
      </div>
    </section>
  );
}
