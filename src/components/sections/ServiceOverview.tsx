import Link from "next/link";
import { services } from "@/data/services";

export function ServiceOverview() {
  return (
    <section className="border-b border-[var(--color-line)] py-24 md:py-32" aria-labelledby="services-heading">
      <div className="container-edge">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--color-blood-red)]">
          Capabilities
        </p>
        <h2 id="services-heading" className="mt-4 max-w-2xl font-display text-4xl uppercase text-[var(--color-off-white)] md:text-5xl">
          What I build
        </h2>
      </div>

      <ul className="mt-16 border-t border-[var(--color-line)]">
        {services.map((service, index) => (
          <li key={service.slug} className="border-b border-[var(--color-line)]">
            <Link
              href={`/services/${service.slug}`}
              className="group container-edge grid grid-cols-1 items-center gap-4 py-8 transition-colors hover:bg-[var(--color-surface)] md:grid-cols-[80px_1fr_auto_auto]"
            >
              <span className="font-mono text-sm text-[var(--color-muted)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="font-display text-2xl uppercase text-[var(--color-off-white)] transition-colors group-hover:text-[var(--color-blood-red)] md:text-3xl">
                {service.name}
              </span>
              <span className="hidden max-w-xs text-sm text-[var(--color-muted)] md:block">
                {service.tagline}
              </span>
              <span
                aria-hidden="true"
                className="hidden font-mono text-lg text-[var(--color-muted)] transition-transform group-hover:translate-x-1 group-hover:text-[var(--color-blood-red)] md:block"
              >
                →
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
