import { asLocale } from "@/i18n/route-locale";
import { notFound } from "next/navigation";
import { QuranReader } from "@/components/quran-reader";

export default async function SurahPage({params}:{params:Promise<{locale:string;surah:string}>}) {
  const {locale:rawLocale,surah}=await params;const locale=asLocale(rawLocale); const number=Number(surah);
  if(!Number.isInteger(number)||number<1||number>114) notFound();
  return <QuranReader locale={locale} surahNumber={number}/>;
}
