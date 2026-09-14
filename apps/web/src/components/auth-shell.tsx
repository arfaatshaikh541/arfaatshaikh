import type { Locale } from "@world-of-islam/shared-types";
import { Brand } from "./brand";
import { LocaleSwitcher } from "./locale-switcher";
import { getMessages } from "@/i18n/messages";
export function AuthShell({ locale, title, description, children }: { locale: Locale; title: string; description: string; children: React.ReactNode }) {
  const t=getMessages(locale);
  return <main className="auth-layout"><section className="auth-intro"><div className="topbar"><Brand locale={locale}/><LocaleSwitcher locale={locale} label={t.language}/></div><div><p className="eyebrow">{t.tagline}</p><h1>{title}</h1><p>{description}</p></div><p className="trust-note">No Islamic source content or AI answers are present in this foundation milestone.</p></section><section className="auth-panel">{children}</section></main>;
}
