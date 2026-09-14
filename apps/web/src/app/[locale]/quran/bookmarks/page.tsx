import { QuranBookmarks } from "@/components/quran-bookmarks";
export default async function Page({params}:{params:Promise<{locale:string}>}){const {locale}=await params;return <QuranBookmarks locale={locale==="ar"?"ar":"en"}/>;}
