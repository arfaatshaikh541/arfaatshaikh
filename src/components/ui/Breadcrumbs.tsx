import Link from "next/link";

export interface Crumb {
  name: string;
  path: string;
}

export default function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="border-b border-line bg-black-near">
      <ol className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-2 px-6 py-4 font-mono text-[11px] uppercase tracking-[0.14em] text-muted md:px-10">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          return (
            <li key={item.path} className="flex items-center gap-2">
              {i > 0 && <span aria-hidden="true">/</span>}
              {isLast ? (
                <span className="text-orange-bright" aria-current="page">
                  {item.name}
                </span>
              ) : (
                <Link href={item.path} className="hover:text-warmwhite transition-colors">
                  {item.name}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
