import Link from "next/link";
import JsonLd from "./JsonLd";
import { breadcrumbSchema } from "@/lib/schema";

export type Crumb = { name: string; path: string };

export default function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="border-b border-gk-graphite bg-gk-black px-5 py-4 sm:px-8">
      <JsonLd data={breadcrumbSchema(items)} />
      <ol className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-2 font-mono-tech text-[0.7rem] uppercase tracking-[0.12em] text-gk-grey-dim">
        {items.map((item, i) => (
          <li key={item.path} className="flex items-center gap-2">
            {i > 0 && <span aria-hidden="true">/</span>}
            {i === items.length - 1 ? (
              <span className="text-gk-orange" aria-current="page">
                {item.name}
              </span>
            ) : (
              <Link href={item.path} className="hover:text-gk-white">
                {item.name}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
