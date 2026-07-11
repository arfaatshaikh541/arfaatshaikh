import Link from "next/link";
import Logo from "@/components/ui/Logo";
import { footerServiceLinks, footerCompanyLinks, footerLegalLinks } from "@/data/nav";
import { CONTACT_EMAIL, LOCATION } from "@/lib/constants";

const features = [
  { title: "Founder Led", desc: "Direct accountability" },
  { title: "Systems Thinking", desc: "Built for long term" },
  { title: "Secure & Reliable", desc: "Privacy by design" },
  { title: "Scalable Solutions", desc: "Grow with confidence" },
];

export default function Footer() {
  return (
    <footer className="border-t border-line bg-black-near">
      <div className="mx-auto max-w-[1440px] px-6 py-14 md:px-10">
        <div className="grid grid-cols-2 gap-8 border-b border-line pb-12 sm:grid-cols-4">
          {features.map((f) => (
            <div key={f.title} className="flex flex-col gap-3">
              <span className="flex h-10 w-10 items-center justify-center border border-line text-orange-primary" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.2" />
                  <circle cx="8" cy="8" r="2" fill="currentColor" />
                </svg>
              </span>
              <div>
                <p className="font-display text-sm uppercase tracking-wide text-warmwhite">{f.title}</p>
                <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-12 py-12 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div className="flex flex-col gap-4">
            <Logo />
            <p className="max-w-xs text-sm text-muted">
              Building intelligent systems for the future of business.
            </p>
          </div>

          <nav aria-label="Services">
            <p className="gk-eyebrow mb-4">Services</p>
            <ul className="flex flex-col gap-2.5">
              {footerServiceLinks.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-warmwhite/80 hover:text-orange-bright">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Company">
            <p className="gk-eyebrow mb-4">Company</p>
            <ul className="flex flex-col gap-2.5">
              {footerCompanyLinks.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-warmwhite/80 hover:text-orange-bright">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <p className="gk-eyebrow mb-4">Legal</p>
            <ul className="flex flex-col gap-2.5">
              {footerLegalLinks.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-warmwhite/80 hover:text-orange-bright">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
            <p className="gk-eyebrow mb-4 mt-8">Connect</p>
            <a href={`mailto:${CONTACT_EMAIL}`} className="block text-sm text-warmwhite/80 hover:text-orange-bright">
              {CONTACT_EMAIL}
            </a>
            <p className="mt-2 text-sm text-muted">{LOCATION}</p>
          </div>
        </div>

        <div className="gk-divider" />

        <div className="flex flex-col items-center gap-2 pt-10 text-center">
          <span className="font-display text-2xl uppercase tracking-wide text-warmwhite md:text-3xl">GRIDKEEP</span>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
            Building Intelligent Systems For The Future Of Business.
          </p>
          <p className="mt-6 text-xs text-muted">© {new Date().getFullYear()} GRIDKEEP. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
