import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { QuranIndex } from "@/components/quran-index";

export default async function QuranPage({params}:{params:Promise<{locale:Locale}>}) {
  const {locale}=await params;
  const arabic=locale==="ar";
  return <main className="quran-landing">
    <header className="topbar"><Brand locale={locale}/><LocaleSwitcher locale={locale} label={arabic?"اللغة":"Language"}/></header>
    <section className="quran-hero">
      <p className="eyebrow">{arabic?"عالم القرآن":"Qur’an Universe"}</p>
      <h1>{arabic?"القرآن الكريم":"The Qur’an"}</h1>
      <p>{arabic?"النص العربي بالرسم العثماني برواية حفص عن عاصم، مع تسجيل مصدر كل آية.":"Arabic text in the Uthmani script, Ḥafṣ ʿan ʿĀṣim, with the source of every ayah recorded."}</p>
      <QuranIndex locale={locale}/>
      <Link className="text-link" href={`/${locale}`}>{arabic?"العودة للرئيسية":"Return home"}</Link>
    </section>
  </main>
}
