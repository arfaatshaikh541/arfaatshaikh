import Link from "next/link";
import { siteConfig } from "@/lib/seo";

export function ContactCta() {
  return (
    <section className="py-24 md:py-40" aria-labelledby="contact-cta-heading">
      <div className="container-edge">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Start a Project
        </p>
        <h2
          id="contact-cta-heading"
          className="text-balance mt-4 max-w-3xl font-display text-4xl uppercase leading-[0.95] text-[var(--color-off-white)] sm:text-5xl md:text-6xl"
        >
          Have a system worth building properly?
        </h2>
        <p className="mt-6 max-w-xl text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
          Tell me about the problem, not just the tool you think you need. I&apos;ll
          reply with an honest read on scope and whether it&apos;s a fit.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <Link
            href="/contact"
            className="inline-flex items-center gap-3 border border-[var(--color-blood-red)] bg-[var(--color-blood-red)] px-8 py-4 font-mono text-xs uppercase tracking-[0.15em] text-black transition-colors hover:bg-transparent hover:text-[var(--color-blood-red)]"
          >
            Start the conversation →
          </Link>
          <a
            href={`mailto:${siteConfig.email}`}
            className="inline-flex items-center gap-3 border border-[var(--color-line)] px-8 py-4 font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
          >
            {siteConfig.email}
          </a>
        </div>
      </div>
    </section>
  );
}
