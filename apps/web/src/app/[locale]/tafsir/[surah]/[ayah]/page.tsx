import {notFound} from 'next/navigation';
import {TafsirReader} from '@/components/tafsir-reader';
export default async function Page({params}:{params:Promise<{locale:string;surah:string;ayah:string}>}){const p=await params;const surah=Number(p.surah),ayah=Number(p.ayah);if(!Number.isInteger(surah)||surah<1||surah>114||!Number.isInteger(ayah)||ayah<1)notFound();return <TafsirReader locale={p.locale} surah={surah} ayah={ayah}/>;}
