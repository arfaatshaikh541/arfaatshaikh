import Link from "next/link";
import { JsonLd } from "./JsonLd";
import { breadcrumbSchema } from "@/lib/schema";

export function Breadcrumbs({ items }: { items: { name: string; path: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mx-auto max-w-[1600px] px-6 pt-28 md:px-10">
      <JsonLd data={breadcrumbSchema(items)} />
      <ol className="flex flex-wrap items-center gap-2 font-mono text-[11px] uppercase tracking-widest2 text-muted">
        {items.map((item, index) => (
          <li key={item.path} className="flex items-center gap-2">
            {index > 0 && <span aria-hidden="true">/</span>}
            {index === items.length - 1 ? (
              <span aria-current="page" className="text-orange">
                {item.name}
              </span>
            ) : (
              <Link href={item.path} className="hover:text-orange">
                {item.name}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
