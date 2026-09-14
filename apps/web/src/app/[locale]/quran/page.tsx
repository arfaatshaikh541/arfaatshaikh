import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";

export default async function QuranPage({params}:{params:Promise<{locale:Locale}>}) {
  const {locale}=await params;
  const arabic=locale==="ar";
  return <main className="quran-landing">
    <header className="topbar"><Brand locale={locale}/><LocaleSwitcher locale={locale} label={arabic?"اللغة":"Language"}/></header>
    <section className="quran-hero">
      <p className="eyebrow">{arabic?"عالم القرآن":"Qur’an Universe"}</p>
      <h1>{arabic?"قراءة موثقة، بلا اختلاق":"Verified reading, without invention"}</h1>
      <p>{arabic?"هذه الواجهة لا تعرض أي نص قرآني حتى يتم اعتماد مصدره وترخيصه والتحقق من سلامته ومراجعته.":"This interface publishes no Qur’anic text until its source, licence, integrity, and scholarly review have all passed."}</p>
      <div className="trust-banner" role="status">{arabic?"لا توجد مجموعة قرآنية معتمدة مستوردة بعد.":"No approved Qur’an corpus has been imported yet."}</div>
      <Link className="text-link" href={`/${locale}`}>{arabic?"العودة للرئيسية":"Return home"}</Link>
    </section>
    <section className="quran-shell" aria-label={arabic?"أساس تجربة القراءة":"Reading experience foundation"}>
      <article><span>01</span><h2>{arabic?"النص العربي هو الأصل":"Arabic remains canonical"}</h2><p>{arabic?"تُحفظ الترجمات كأعمال مستقلة مع نسبتها وترخيصها.":"Translations remain separate attributed works with independent licensing."}</p></article>
      <article><span>02</span><h2>{arabic?"إسناد على مستوى الآية":"Ayah-level provenance"}</h2><p>{arabic?"كل آية ترتبط بمقطع مصدر ثابت وبصمة تشفيرية.":"Every ayah links to an immutable source passage and cryptographic digest."}</p></article>
      <article><span>03</span><h2>{arabic?"الإغلاق عند الفشل":"Fail closed"}</h2><p>{arabic?"أي خلل في التحقق يمنع النشر.":"Any failed trust gate prevents publication."}</p></article>
    </section>
  </main>
}
