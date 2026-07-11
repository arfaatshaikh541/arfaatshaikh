import Link from "next/link";
import { CONTACT_EMAIL, FOOTER_LEGAL_LINKS, LOCATION, NAV_LINKS } from "@/lib/constants";

export function Footer() {
  return (
    <footer className="border-t border-line bg-black">
      <div className="mx-auto max-w-[1600px] px-6 py-16 md:px-10">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-4">
          <div className="md:col-span-2">
            <span className="font-display text-2xl tracking-widest2 text-warm">GRIDKEEP</span>
            <p className="mt-4 max-w-sm text-sm text-muted">
              A founder-led technology systems company designing AI, automation, software,
              cybersecurity, cloud infrastructure, and immersive digital experiences.
            </p>
            <p className="mt-4 font-mono text-xs uppercase tracking-widest2 text-muted">
              {LOCATION}
            </p>
          </div>

          <div>
            <span className="font-mono text-xs uppercase tracking-widest2 text-orange">Navigate</span>
            <ul className="mt-4 flex flex-col gap-3">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-warm hover:text-orange">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <span className="font-mono text-xs uppercase tracking-widest2 text-orange">Contact</span>
            <ul className="mt-4 flex flex-col gap-3">
              <li>
                <a href={`mailto:${CONTACT_EMAIL}`} className="text-sm text-warm hover:text-orange">
                  {CONTACT_EMAIL}
                </a>
              </li>
              {FOOTER_LEGAL_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-warm hover:text-orange">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-16 flex flex-col gap-4 border-t border-line pt-8 text-xs text-muted md:flex-row md:items-center md:justify-between">
          <span>© {new Date().getFullYear()} GRIDKEEP. Founder-led technology systems.</span>
          <span className="font-mono uppercase tracking-widest2">Built by Arfaat Shaikh</span>
        </div>
      </div>
    </footer>
  );
}
