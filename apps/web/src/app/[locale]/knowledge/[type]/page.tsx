import { notFound } from "next/navigation";
import { KnowledgeBrowser } from "@/components/knowledge-browser";
import { KNOWLEDGE_TYPES } from "@/lib/copy";
import { asLocale } from "@/i18n/route-locale";

export default async function KnowledgeTypePage({ params }: { params: Promise<{ locale: string; type: string }> }) {
  const { locale: rawLocale, type } = await params;
  const locale = asLocale(rawLocale);
  if (!KNOWLEDGE_TYPES.some((t) => t.id === type)) notFound();
  return <KnowledgeBrowser locale={locale} type={type} />;
}
