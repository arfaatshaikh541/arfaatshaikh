"use client";

import { useEffect, useState, type KeyboardEvent } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api";

type Translation = { id:string; translation_key:string; language:string; translator_name:string; display_name:string };
type Ayah = { id:string; canonical_reference:string; ayah_number:number; arabic_text:string; juz_number:number|null; page_number:number|null; translation:string|null; translation_edition_id:string|null };
type Recitation = { id:string; recitation_key:string; reciter_name:string; riwayah:string; display_name:string; attribution_text:string };
type AudioAyah = { id:string; ayah_id:string; canonical_reference:string; audio_url:string; duration_ms:number };
type Reading = { surah:{surah_number:number; arabic_name:string; transliterated_name:string; english_name:string; ayah_count:number; revelation_classification:string}; translation:Translation|null; ayahs:Ayah[]; next_surah_number:number|null; previous_surah_number:number|null };

export function QuranReader({ locale, surahNumber }:{locale:"en"|"ar";surahNumber:number}) {
  const arabic = locale === "ar";
  const [translations,setTranslations]=useState<Translation[]>([]);
  const [selected,setSelected]=useState("");
  const [reading,setReading]=useState<Reading|null>(null);
  const [message,setMessage]=useState(arabic?"جارٍ تحميل السورة…":"Loading surah…");
  const [fontScale,setFontScale]=useState(100);
  const [recitations,setRecitations]=useState<Recitation[]>([]);
  const [recitation,setRecitation]=useState("");
  const [audio,setAudio]=useState<Record<string,AudioAyah>>({});
  const [repeatMode,setRepeatMode]=useState<"off"|"ayah"|"surah">("off");

  useEffect(()=>{
    Promise.all([
      apiFetch<Translation[]>("/quran/translations").catch(()=>[]),
      apiFetch<Recitation[]>("/quran/recitations").catch(()=>[]),
      apiFetch<{translation_edition_id:string|null;show_translation:boolean;arabic_font_scale:number}>("/quran/me/preferences").catch(()=>null),
    ]).then(([availableTranslations,availableRecitations,preferences])=>{
      setTranslations(availableTranslations); setRecitations(availableRecitations);
      if(preferences){ setFontScale(preferences.arabic_font_scale); const selectedTranslation=availableTranslations.find(item=>item.id===preferences.translation_edition_id); if(preferences.show_translation&&selectedTranslation)setSelected(selectedTranslation.translation_key); }
    });
  },[]);
  useEffect(()=>{
    setReading(null); setMessage(arabic?"جارٍ تحميل السورة…":"Loading surah…");
    const query=selected?`?translation=${encodeURIComponent(selected)}`:"";
    apiFetch<Reading>(`/quran/surahs/${surahNumber}/reading${query}`).then(data=>{setReading(data);setMessage("");}).catch((error:unknown)=>{
      setMessage(error instanceof ApiError && error.code==="quran_corpus_unavailable" ? (arabic?"لا توجد نسخة قرآنية معتمدة ومنشورة بعد.":"No approved canonical Qur’an edition is published yet.") : (arabic?"تعذر تحميل السورة.":"The surah could not be loaded."));
    });
  },[arabic,selected,surahNumber]);


  useEffect(()=>{
    if(!recitation){setAudio({});return;}
    apiFetch<AudioAyah[]>(`/quran/surahs/${surahNumber}/audio?recitation=${encodeURIComponent(recitation)}`).then(rows=>setAudio(Object.fromEntries(rows.map(row=>[row.ayah_id,row])))).catch(()=>setAudio({}));
  },[recitation,surahNumber]);
  function onKeyDown(event:KeyboardEvent<HTMLElement>){
    if(event.altKey && event.key==="ArrowRight" && reading?.next_surah_number) window.location.href=`/${locale}/quran/${reading.next_surah_number}`;
    if(event.altKey && event.key==="ArrowLeft" && reading?.previous_surah_number) window.location.href=`/${locale}/quran/${reading.previous_surah_number}`;
  }

  async function persistPlayback(item:AudioAyah, element:HTMLAudioElement){
    try { await apiFetch("/quran/me/playback",{method:"PUT",body:JSON.stringify({ayah_audio_id:item.id,position_ms:Math.floor(element.currentTime*1000),repeat_mode:repeatMode,playback_rate:Math.round(element.playbackRate*100)})}); } catch {}
  }
  function handleAudioEnded(element:HTMLAudioElement){
    if(repeatMode==="ayah"){ element.currentTime=0; void element.play(); return; }
    if(repeatMode==="surah"){ const players=Array.from(document.querySelectorAll<HTMLAudioElement>("audio[data-quran-audio]")); const index=players.indexOf(element); const next=players[index+1]??players[0]; if(next){next.currentTime=0;void next.play();} }
  }

  async function bookmark(ayah:Ayah){
    try { await apiFetch("/quran/me/bookmarks",{method:"POST",body:JSON.stringify({ayah_id:ayah.id})}); setMessage(arabic?`تم حفظ ${ayah.canonical_reference}`:`Bookmarked ${ayah.canonical_reference}`); }
    catch { setMessage(arabic?"سجّل الدخول لحفظ العلامات.":"Sign in to save bookmarks."); }
  }
  async function copyCitation(ayah:Ayah){
    const url=`${window.location.origin}/${locale}/quran/${surahNumber}#ayah-${ayah.ayah_number}`;
    const text=`${ayah.arabic_text}${ayah.translation?`\n${ayah.translation}`:""}\nQur’an ${ayah.canonical_reference}\n${url}`;
    try { await navigator.clipboard.writeText(text); setMessage(arabic?"تم نسخ الآية مع المرجع.":"Ayah and citation copied."); } catch { setMessage(arabic?"تعذر النسخ.":"Copy failed."); }
  }
  async function savePreferences(){
    const translation=translations.find(t=>t.translation_key===selected);
    try { await apiFetch("/quran/me/preferences",{method:"PUT",body:JSON.stringify({translation_edition_id:translation?.id??null,show_translation:Boolean(selected),arabic_font_scale:fontScale,theme:"system"})}); setMessage(arabic?"تم حفظ تفضيلات القارئ.":"Reader preferences saved."); } catch { setMessage(arabic?"سجّل الدخول لحفظ التفضيلات.":"Sign in to save preferences."); }
  }
  async function saveProgress(ayah:Ayah){
    try { await apiFetch("/quran/me/progress",{method:"PUT",body:JSON.stringify({ayah_id:ayah.id,translation_edition_id:ayah.translation_edition_id})}); setMessage(arabic?`تم حفظ موضع القراءة عند ${ayah.canonical_reference}`:`Reading position saved at ${ayah.canonical_reference}`); }
    catch { setMessage(arabic?"سجّل الدخول لحفظ موضع القراءة.":"Sign in to save reading progress."); }
  }

  return <main className="quran-reader-page" onKeyDown={onKeyDown}>
    <header className="reader-toolbar">
      <Link href={`/${locale}/quran`}>{arabic?"فهرس السور":"Surah index"}</Link>
      <label>{arabic?"الترجمة":"Translation"}<select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">{arabic?"بدون ترجمة":"Arabic only"}</option>{translations.map(t=><option key={t.id} value={t.translation_key}>{t.display_name}</option>)}</select></label><label>{arabic?"حجم الخط":"Arabic size"}<input aria-label={arabic?"حجم الخط العربي":"Arabic font size"} type="range" min="80" max="200" value={fontScale} onChange={e=>setFontScale(Number(e.target.value))}/></label><label>{arabic?"القارئ":"Reciter"}<select value={recitation} onChange={e=>setRecitation(e.target.value)}><option value="">{arabic?"بدون صوت":"No audio"}</option>{recitations.map(r=><option key={r.id} value={r.recitation_key}>{r.display_name}</option>)}</select></label><label>{arabic?"التكرار":"Repeat"}<select value={repeatMode} onChange={e=>setRepeatMode(e.target.value as "off"|"ayah"|"surah")}><option value="off">{arabic?"إيقاف":"Off"}</option><option value="ayah">{arabic?"الآية":"Ayah"}</option><option value="surah">{arabic?"السورة":"Surah"}</option></select></label><button onClick={savePreferences}>{arabic?"حفظ التفضيلات":"Save preferences"}</button><Link href={`/${locale}/quran/bookmarks`}>{arabic?"علاماتي":"My bookmarks"}</Link>
    </header>
    {message && <div className="trust-banner" role="status">{message}</div>}
    {reading && <>
      <section className="surah-heading"><p>{reading.surah.revelation_classification}</p><h1>{reading.surah.arabic_name}</h1><h2>{reading.surah.transliterated_name}</h2><span>{reading.surah.ayah_count} {arabic?"آية":"ayahs"}</span></section>
      <ol className="ayah-list">{reading.ayahs.map(ayah=><li id={`ayah-${ayah.ayah_number}`} key={ayah.id} className="ayah-card">
        <div className="ayah-meta"><a href={`#ayah-${ayah.ayah_number}`}>{ayah.canonical_reference}</a><span>{ayah.page_number?`${arabic?"صفحة":"Page"} ${ayah.page_number}`:""}</span></div>
        <p className="ayah-arabic" dir="rtl" lang="ar" style={{fontSize:`${fontScale}%`}}>{ayah.arabic_text}</p>
        {ayah.translation && <p className="ayah-translation">{ayah.translation}</p>}{audio[ayah.id]&&<audio data-quran-audio controls preload="none" src={audio[ayah.id].audio_url} onPause={e=>void persistPlayback(audio[ayah.id],e.currentTarget)} onEnded={e=>handleAudioEnded(e.currentTarget)} aria-label={`${arabic?"تلاوة":"Recitation"} ${ayah.canonical_reference}`}/>}
        <div className="ayah-actions"><button onClick={()=>bookmark(ayah)}>{arabic?"حفظ":"Bookmark"}</button><button onClick={()=>saveProgress(ayah)}>{arabic?"حفظ موضع القراءة":"Save position"}</button><button onClick={()=>copyCitation(ayah)}>{arabic?"نسخ مع المرجع":"Copy citation"}</button></div>
      </li>)}</ol>
      <nav className="surah-pagination">{reading.previous_surah_number&&<Link href={`/${locale}/quran/${reading.previous_surah_number}`}>{arabic?"السورة السابقة":"Previous surah"}</Link>}{reading.next_surah_number&&<Link href={`/${locale}/quran/${reading.next_surah_number}`}>{arabic?"السورة التالية":"Next surah"}</Link>}</nav>
    </>}
  </main>;
}
