import type { Locale } from "@world-of-islam/shared-types";
import { notFound } from "next/navigation";
import { QuranReader } from "@/components/quran-reader";

export default async function SurahPage({params}:{params:Promise<{locale:Locale;surah:string}>}) {
  const {locale,surah}=await params; const number=Number(surah);
  if(!Number.isInteger(number)||number<1||number>114) notFound();
  return <QuranReader locale={locale} surahNumber={number}/>;
}
