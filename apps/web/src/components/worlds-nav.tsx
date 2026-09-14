import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { worlds } from "@/lib/worlds";

// A native <details>/<summary> disclosure: keyboard- and screen-reader
// accessible without any JS state, and naturally avoids the header-overflow
// problem twelve world names have at any fixed width - it never needs to
// fit more than one label ("Worlds") in the header itself.
export function WorldsNav({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  return (
    <details className="worlds-nav">
      <summary>{ar ? "العوالم" : "Worlds"}</summary>
      <ul>
        {worlds.map((w) => (
          <li key={w.slug}>
            <Link href={`/${locale}/w/${w.slug}`}>{ar ? w.nameAr : w.name}</Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
