"use client";
import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@world-of-islam/ui";
import { useAuth } from "./auth-provider";
import { Brand } from "./brand";
import { LocaleSwitcher } from "./locale-switcher";
import { WorldsNav } from "./worlds-nav";
import { getMessages } from "@/i18n/messages";

export function ProtectedShell({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const t=getMessages(locale); const auth=useAuth(); const router=useRouter();
  useEffect(()=>{ if(!auth.loading && !auth.user) router.replace(`/${locale}/login`); },[auth.loading,auth.user,locale,router]);
  if(auth.loading || !auth.user) return <main className="centered" aria-live="polite">{t.loading}</main>;
  return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to content</a><header className="app-header"><Brand locale={locale}/><WorldsNav locale={locale}/><nav aria-label="Primary"><Link href={`/${locale}/dashboard`}>{t.dashboard}</Link></nav><div className="header-actions"><LocaleSwitcher locale={locale} label={t.language}/><Button className="button-quiet" onClick={async()=>{await auth.logout();router.replace(`/${locale}/login`);}}>{t.signOut}</Button></div></header><main id="main-content" className="app-main">{children}</main></div>;
}
