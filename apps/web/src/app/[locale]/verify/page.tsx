import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { TextVerifier } from "@/components/text-verifier";
import { getMessages } from "@/i18n/messages";

export default async function VerifyPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
  const ar = locale === "ar";
  const t = getMessages(locale);
  return (
    <main className="world-page">
      <header className="topbar">
        <Brand locale={locale} />
        <WorldsNav locale={locale} />
        <LocaleSwitcher locale={locale} label={t.language} />
      </header>
      <header className="world-page-hero">
        <Link className="text-link" href={`/${locale}/w`}>{ar ? "كل العوالم" : "All worlds"}</Link>
        <h1>{ar ? "التحقق من النص" : "Text verification"}</h1>
        <p>
          {ar ? "تحقق مما إذا كان نص عربي يرد حرفياً في القرآن أو في كتب الحديث المنشورة." : "Check whether an Arabic passage appears word for word in the published Qur’an or Hadith text."}
        </p>
      </header>
      <TextVerifier locale={locale} />
    </main>
  );
}
