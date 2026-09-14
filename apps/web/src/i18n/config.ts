import type { Locale } from "@world-of-islam/shared-types";

export const locales: readonly Locale[] = ["en", "ar"];
export const defaultLocale: Locale = "en";
export function isLocale(value: string): value is Locale { return locales.includes(value as Locale); }
export function direction(locale: Locale): "ltr" | "rtl" { return locale === "ar" ? "rtl" : "ltr"; }
