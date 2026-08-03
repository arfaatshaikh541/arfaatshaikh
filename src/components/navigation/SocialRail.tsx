import { siteConfig } from "@/lib/seo";

// A persistent chrome element down the left edge of the viewport. Only a
// mail icon here, deliberately — LinkedIn/GitHub/Instagram icons would need
// real profile URLs, and this project's brief is explicit about not
// inventing anything, dead "#" social links included.
export function SocialRail() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-y-0 left-0 z-40 hidden w-14 flex-col items-center justify-between py-28 2xl:flex"
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-[var(--color-muted)] [writing-mode:vertical-rl]">
        Scroll
      </span>

      <div className="flex flex-col items-center gap-5">
        <span className="h-16 w-px bg-[var(--color-line)]" />
        <a
          href={`mailto:${siteConfig.email}`}
          aria-label={`Email ${siteConfig.email}`}
          className="pointer-events-auto text-[var(--color-muted)] transition-colors hover:text-[var(--color-blood-red)]"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="2.5" y="4.5" width="19" height="15" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M3.5 6L12 13L20.5 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </a>
      </div>
    </div>
  );
}
