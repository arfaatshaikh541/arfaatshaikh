import type { Locale } from "@world-of-islam/shared-types";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { AuthProvider } from "@/components/auth-provider";
import { CommandPalette } from "@/components/command-palette";
import { direction, isLocale } from "@/i18n/config";

export const dynamic = "force-dynamic";

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();

  return (
    <div lang={locale} dir={direction(locale as Locale)}>
      <AuthProvider>{children}</AuthProvider>
      <div className="command-trigger-dock">
        <CommandPalette locale={locale as Locale} />
      </div>
    </div>
  );
}
