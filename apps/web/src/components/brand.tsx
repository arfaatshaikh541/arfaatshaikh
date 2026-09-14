import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { getMessages } from "@/i18n/messages";
export function Brand({ locale }: { locale: Locale }) {
  const t = getMessages(locale);
  return <Link className="brand" href={`/${locale}`} aria-label={t.brand}><span className="brand-mark" aria-hidden="true">◇</span><span>{t.brand}</span></Link>;
}
