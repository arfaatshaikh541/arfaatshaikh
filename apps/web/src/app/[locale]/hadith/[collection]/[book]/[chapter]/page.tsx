import { HadithReader } from "@/components/hadith-reader";

export default async function HadithChapterPage({ params }: { params: Promise<{ locale: string; collection: string; book: string; chapter: string }> }) {
  const { locale, collection, book, chapter } = await params;
  return <HadithReader locale={locale} collection={collection} book={Number(book)} chapter={Number(chapter)} />;
}
