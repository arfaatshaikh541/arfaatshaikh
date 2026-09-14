"use client";
import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function LocaleSwitcher({ locale, label }: { locale: Locale; label: string }) {
  const pathname = usePathname();
  const next = locale === "en" ? "ar" : "en";
  const target = pathname.replace(/^\/(en|ar)(?=\/|$)/, `/${next}`);
  return <Link className="text-link locale-switcher" href={target} hrefLang={next}>{label}</Link>;
}
