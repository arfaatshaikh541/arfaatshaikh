import { IslamicAssistant } from "../../../components/islamic-assistant";

export default async function AssistantPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  return <IslamicAssistant locale={locale === "ar" ? "ar" : "en"} />;
}
