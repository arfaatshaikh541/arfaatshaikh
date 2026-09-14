import { LearningDashboard } from '@/components/learning-dashboard';
export default async function LearningPage({ params }: { params: Promise<{ locale: string }> }) {
 const { locale }=await params;
 return <LearningDashboard locale={locale==='ar'?'ar':'en'} />;
}
