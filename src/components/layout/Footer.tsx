import Link from "next/link";
import { services } from "@/data/services";
import { siteConfig } from "@/lib/seo";

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-[var(--color-line)] bg-black">
      <div className="container-edge grid gap-12 py-16 md:grid-cols-4">
        <div className="md:col-span-2">
          <p className="font-display text-2xl uppercase text-[var(--color-off-white)]">
            Arfaat Shaikh
          </p>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-[var(--color-muted)]">
            Creative Engineer based in the United Arab Emirates. Founder of{" "}
            <a
              href={siteConfig.gridkeepUrl}
              className="text-[var(--color-off-white)] underline decoration-[var(--color-blood-red)] underline-offset-4"
            >
              GRIDKEEP
            </a>
            , building AI systems, software, and immersive web experiences.
          </p>
          <a
            href={`mailto:${siteConfig.email}`}
            className="mt-6 inline-block font-mono text-sm text-[var(--color-blood-red)]"
          >
            {siteConfig.email}
          </a>
        </div>

        <nav aria-label="Services">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-[var(--color-muted)]">
            Services
          </p>
          <ul className="mt-4 space-y-3">
            {services.map((service) => (
              <li key={service.slug}>
                <Link
                  href={`/services/${service.slug}`}
                  className="text-sm text-[var(--color-off-white)] transition-colors hover:text-[var(--color-blood-red)]"
                >
                  {service.shortName}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-label="Site">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-[var(--color-muted)]">
            Site
          </p>
          <ul className="mt-4 space-y-3">
            {[
              { label: "About", href: "/about" },
              { label: "Projects", href: "/projects" },
              { label: "GRIDKEEP", href: "/gridkeep" },
              { label: "Insights", href: "/insights" },
              { label: "Contact", href: "/contact" },
              { label: "Privacy Policy", href: "/privacy" },
              { label: "Terms & Conditions", href: "/terms" },
            ].map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="text-sm text-[var(--color-off-white)] transition-colors hover:text-[var(--color-blood-red)]"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>

      <div className="container-edge flex flex-col gap-2 border-t border-[var(--color-line)] py-6 font-mono text-xs text-[var(--color-muted)] md:flex-row md:items-center md:justify-between">
        <p>© {year} Arfaat Shaikh. All rights reserved.</p>
        <p>United Arab Emirates</p>
      </div>
    </footer>
  );
}
