import Link from "next/link";
import { FOOTER_NAV, SITE } from "@/lib/site";

export default function SiteFooter() {
  return (
    <footer className="gk-grid-bg border-t border-gk-steel bg-gk-black">
      <div className="mx-auto max-w-[1600px] px-5 py-16 sm:px-8">
        <div className="grid grid-cols-1 gap-12 border-b border-gk-graphite pb-12 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Link href="/" className="font-display text-2xl font-bold tracking-[0.06em] text-gk-white">
              GRID<span className="gk-orange-text">KEEP</span>
            </Link>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-gk-grey">{SITE.description}</p>
            <dl className="mt-6 space-y-1 font-mono-tech text-xs uppercase tracking-[0.1em] text-gk-grey">
              <div className="flex gap-2">
                <dt className="text-gk-grey-dim">Founder</dt>
                <dd className="text-gk-white">{SITE.founder}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-gk-grey-dim">Base</dt>
                <dd className="text-gk-white">{SITE.location}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-gk-grey-dim">Contact</dt>
                <dd>
                  <a href={`mailto:${SITE.email}`} className="text-gk-orange hover:text-gk-orange-bright">
                    {SITE.email}
                  </a>
                </dd>
              </div>
            </dl>
          </div>

          {FOOTER_NAV.map((group) => (
            <div key={group.title}>
              <h2 className="gk-eyebrow mb-4">{group.title}</h2>
              <ul className="space-y-2.5">
                {group.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-gk-grey transition-colors hover:text-gk-white">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="flex flex-col items-start justify-between gap-4 pt-8 font-mono-tech text-[0.7rem] uppercase tracking-[0.14em] text-gk-grey-dim sm:flex-row sm:items-center">
          <span>&copy; {new Date().getFullYear()} GRIDKEEP. System status: operational.</span>
          <span>Engineered in the United Arab Emirates.</span>
        </div>
      </div>
    </footer>
  );
}
