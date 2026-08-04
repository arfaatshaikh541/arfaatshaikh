import Link from "next/link";
import { valueProps } from "@/data/valueProps";

const ICONS = [
  // Full-Stack — layers
  <svg key="layers" width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 3L2 8l10 5 10-5-10-5Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    <path d="M2 16l10 5 10-5" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
  </svg>,
  // AI-Native — chip
  <svg key="chip" width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="6" y="6" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
    <path
      d="M9 2v3M12 2v3M15 2v3M9 19v3M12 19v3M15 19v3M2 9h3M2 12h3M2 15h3M19 9h3M19 12h3M19 15h3"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
    />
  </svg>,
  // Security by Design — shield
  <svg key="shield" width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 2.5l8 3v6c0 5-3.5 8.5-8 9.5-4.5-1-8-4.5-8-9.5v-6l8-3Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    <path d="M8.5 12l2.5 2.5 4.5-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>,
  // Remote-First — globe
  <svg key="globe" width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="12" cy="12" r="9.5" stroke="currentColor" strokeWidth="1.4" />
    <path d="M2.5 12h19M12 2.5c2.5 2.7 3.8 6 3.8 9.5s-1.3 6.8-3.8 9.5c-2.5-2.7-3.8-6-3.8-9.5S9.5 5.2 12 2.5Z" stroke="currentColor" strokeWidth="1.4" />
  </svg>,
];

export function AboutSnapshot() {
  return (
    <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="about-snapshot-heading">
      <div className="container-edge grid gap-12 lg:grid-cols-[1fr_1.2fr] lg:gap-16">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            About Me
          </p>
          <h2 id="about-snapshot-heading" className="mt-4 max-w-md font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] md:text-5xl">
            Engineering solutions.
            <br />
            Elevating brands.
          </h2>
          <span aria-hidden="true" className="mt-6 block h-px w-16 bg-[var(--color-blood-red)]" />
        </div>

        <div>
          <p className="max-w-2xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
            I&apos;m a Computer Science graduate and full-stack engineer
            specializing in high-performance digital products. From AI
            automations to immersive web experiences, I turn ideas into
            systems businesses can actually run on.
          </p>
          <Link
            href="/about"
            className="mt-6 inline-flex items-center gap-3 font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:text-[var(--color-blood-red)]"
          >
            More about me →
          </Link>

          <ul className="mt-10 grid grid-cols-2 gap-px overflow-hidden border border-[var(--color-line)] bg-[var(--color-line)] sm:grid-cols-4">
            {valueProps.map((prop, index) => (
              <li key={prop.label} className="flex flex-col items-start gap-3 bg-black p-5">
                <span className="text-[var(--color-blood-red)]">{ICONS[index]}</span>
                <span className="font-display text-base uppercase leading-tight text-[var(--color-off-white)]">
                  {prop.label}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.06em] text-[var(--color-muted)]">
                  {prop.caption}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
