import { KnowledgeGraphExplorer } from "@/components/knowledge-graph-explorer";
import { asLocale } from "@/i18n/route-locale";

export default async function GraphPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  return <KnowledgeGraphExplorer locale={asLocale(locale)} />;
}
