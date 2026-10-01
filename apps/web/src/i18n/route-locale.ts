import type { Locale } from "@world-of-islam/shared-types";
import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";

/** Narrows the `[locale]` route segment (always a string at the framework boundary) to a supported locale. */
export function asLocale(value: string): Locale {
  if (!isLocale(value)) notFound();
  return value;
}
