import Link from "next/link";

export function FounderSection() {
  return (
    <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="founder-heading">
      <div className="container-edge grid gap-12 md:grid-cols-2 md:gap-20">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
            Founder
          </p>
          <h2 id="founder-heading" className="mt-4 font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
            Arfaat Shaikh
          </h2>
        </div>
        <div className="space-y-6 text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          <p>
            I hold a Bachelor&apos;s degree in Computer Science and started my
            career in customer service and sales before moving into
            engineering — an unusual path that means I design systems with
            both the technical and commercial side of a business in mind.
          </p>
          <p>
            That combination shapes how I work: I don&apos;t just build what
            is asked for, I try to understand what the business is actually
            trying to achieve, and build the system that gets it there.
          </p>
          <p>
            I&apos;m the founder of{" "}
            <a
              href="https://gridkeep.com"
              className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              GRIDKEEP
            </a>
            , the technology studio behind the engineering work on this site.
          </p>
          <Link
            href="/about"
            className="inline-flex items-center gap-3 font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:text-[var(--color-blood-red)]"
          >
            More about my background →
          </Link>
        </div>
      </div>
    </section>
  );
}
