import Link from "next/link";

export interface Crumb {
  name: string;
  href: string;
}

export function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-2 font-mono text-xs uppercase tracking-[0.1em] text-[var(--color-muted)]">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={crumb.href} className="flex items-center gap-2">
              {index > 0 && <span aria-hidden="true">/</span>}
              {isLast ? (
                <span aria-current="page" className="text-[var(--color-off-white)]">
                  {crumb.name}
                </span>
              ) : (
                <Link href={crumb.href} className="transition-colors hover:text-[var(--color-off-white)]">
                  {crumb.name}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
