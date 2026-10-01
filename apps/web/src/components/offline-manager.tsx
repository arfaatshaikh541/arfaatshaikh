"use client";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { clearSurahs, estimateBytes, isOfflineStorageAvailable, listDownloaded, queuedCount, saveSurah, searchOffline, SURAH_COUNT } from "@/lib/offline";
import Link from "next/link";

type Surah = { surah_number: number; arabic_name: string; transliterated_name: string; english_name: string; ayah_count: number };

export function OfflineManager({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [supported, setSupported] = useState(true);
  const [surahs, setSurahs] = useState<Surah[]>([]);
  const [have, setHave] = useState<number[]>([]);
  const [bytes, setBytes] = useState(0);
  const [queued, setQueued] = useState(0);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ surah: number; text: string }[]>([]);
  const [online, setOnline] = useState(true);

  const refresh = useCallback(async () => {
    if (!isOfflineStorageAvailable()) { setSupported(false); return; }
    setHave((await listDownloaded()).map((r) => r.surah)); setBytes(await estimateBytes()); setQueued(await queuedCount());
  }, []);
  useEffect(() => {
    void refresh();
    apiFetch<Surah[]>("/quran/surahs").then(setSurahs).catch(() => undefined);
    const update = () => setOnline(navigator.onLine);
    update(); window.addEventListener("online", update); window.addEventListener("offline", update);
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); };
  }, [refresh]);

  async function download(numbers: number[]) {
    setError("");
    try {
      for (const n of numbers) {
        setBusy(`${n}/${SURAH_COUNT}`);
        await saveSurah(n, await apiFetch<{ ayahs: { arabic_text: string }[] }>(`/quran/surahs/${n}/reading`));
      }
    } catch { setError(ar ? "تعذّر التنزيل. تحقق من الاتصال وحاول مجدداً." : "Download failed. Check your connection and try again."); }
    setBusy(""); await refresh();
  }
  async function search(e: React.FormEvent) { e.preventDefault(); setHits(await searchOffline(q)); }

  const rows: [string, boolean, string][] = [
    [ar ? "نص القرآن العربي (بعد التنزيل)" : "Qur'an Arabic text (after you download it)", have.length > 0, ar ? "متاح دون اتصال" : "Available offline"],
    [ar ? "البحث في النص المنزَّل" : "Search in the downloaded text", have.length > 0, ar ? "متاح دون اتصال" : "Available offline"],
    [ar ? "الصفحات التي زرتها (الهيكل فقط)" : "Pages you have visited (layout only)", true, ar ? "متاح دون اتصال" : "Available offline"],
    [ar ? "العلامات والتقدم المحفوظ أثناء الانقطاع" : "Bookmarks made while offline", true, ar ? "تُحفظ وتُرسل لاحقاً" : "Queued and synced later"],
    [ar ? "الترجمات والتفسير والحديث" : "Translations, tafsir and hadith", false, ar ? "يتطلب إنترنت" : "Requires internet"],
    [ar ? "المساعد والبحث الموحد والدليل" : "Assistant, unified search and directory", false, ar ? "يتطلب إنترنت" : "Requires internet"],
  ];
  if (!supported) return <main className="knowledge-page"><p role="alert">{ar ? "هذا المتصفح لا يدعم التخزين دون اتصال." : "This browser does not support offline storage."}</p></main>;
  return (
    <main className="knowledge-page" dir={ar ? "rtl" : "ltr"}>
      <h1>{ar ? "القراءة دون اتصال" : "Offline reading"}</h1>
      <p className="tool-note">{online ? (ar ? "أنت متصل." : "You are online.") : (ar ? "أنت غير متصل: يعمل ما نزّلته فقط." : "You are offline: only what you downloaded works.")} {ar ? "تُخزَّن الأشياء على جهازك فقط، ولا تُنزَّل ترجمات ما لم تتأكد حقوقها." : "Everything stays on your device. No translation is downloaded unless its rights are confirmed."}</p>
      <table className="audit-table"><thead><tr><th>{ar ? "الميزة" : "Feature"}</th><th>{ar ? "الحالة" : "Status"}</th></tr></thead>
        <tbody>{rows.map(([name, ok, label]) => <tr key={name}><td>{name}</td><td><span className={`status-pill ${ok ? "status-implemented" : "status-not-implemented"}`}>{label}</span></td></tr>)}</tbody></table>
      <section>
        <h2>{ar ? "القرآن الكريم (النص العربي)" : "Qur'an (Arabic text)"}</h2>
        <p>{have.length} / {SURAH_COUNT} {ar ? "سورة منزَّلة" : "surahs downloaded"} · {(bytes / 1024 / 1024).toFixed(2)} MB · {queued} {ar ? "إجراء بانتظار المزامنة" : "actions waiting to sync"}</p>
        <div className="reader-actions">
          <button disabled={!!busy || !online} onClick={() => download(Array.from({ length: SURAH_COUNT }, (_, i) => i + 1).filter((n) => !have.includes(n)))}>{busy ? `${ar ? "جارٍ التنزيل" : "Downloading"} ${busy}` : ar ? "نزّل القرآن كاملاً" : "Download the whole Qur'an"}</button>
          <button disabled={have.length === 0 || !!busy} onClick={async () => { await clearSurahs(); await refresh(); }}>{ar ? "احذف النسخة المنزَّلة" : "Delete downloaded copy"}</button>
        </div>
        {error && <p role="alert">{error}</p>}
        <div className="knowledge-types" role="group" aria-label={ar ? "السور" : "Surahs"}>
          {surahs.map((s) => <button key={s.surah_number} className={have.includes(s.surah_number) ? "chip chip-active" : "chip"} disabled={!!busy || (!online && !have.includes(s.surah_number))} onClick={() => !have.includes(s.surah_number) && download([s.surah_number])} aria-label={`${s.transliterated_name} ${have.includes(s.surah_number) ? (ar ? "منزَّلة" : "downloaded") : ""}`}>{s.surah_number}. {ar ? s.arabic_name : s.transliterated_name}</button>)}
        </div>
        {surahs.length === 0 && <p className="tool-note">{ar ? "قائمة السور تتطلب اتصالاً أو نشر نص القرآن." : "The surah list needs a connection, or the Qur'an text is not published."}</p>}
      </section>
      <section>
        <h2>{ar ? "ابحث في النص المنزَّل" : "Search the downloaded text"}</h2>
        <form onSubmit={search} role="search"><input value={q} onChange={(e) => setQ(e.target.value)} lang="ar" dir="rtl" placeholder="بحث" aria-label={ar ? "بحث" : "Search"} /><button>{ar ? "بحث" : "Search"}</button></form>
        <ul className="record-list">{hits.map((h, i) => <li key={i} className="record-card"><Link href={`/${locale}/quran/${h.surah}`}>{h.surah}</Link><p className="arabic-text" lang="ar" dir="rtl">{h.text}</p></li>)}</ul>
      </section>
    </main>
  );
}
