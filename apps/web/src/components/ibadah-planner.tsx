"use client";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { computeSalahTimes } from "@/lib/salah";
import { daysBetween, gregorianOfHijri, hijriParts, nextHijriEvent } from "@/lib/hijri";
import { moonAgeDays, moonIllumination, moonPhase, nextPhaseDate, type MoonPhase } from "@/lib/moon";

type Locale = "en" | "ar";
type Coords = { latitude: number; longitude: number };

function load<T>(key: string, fallback: T): T {
  try { const v = window.localStorage.getItem(key); return v ? (JSON.parse(v) as T) : fallback; } catch { return fallback; }
}
function save(key: string, value: unknown) {
  try { window.localStorage.setItem(key, JSON.stringify(value)); } catch { /* best-effort only */ }
}
const dayKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const fmtDate = (d: Date, locale: Locale) => d.toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

const PHASES: Record<MoonPhase, [string, string]> = {
  new: ["New moon", "المحاق"], "waxing-crescent": ["Waxing crescent", "هلال متزايد"], "first-quarter": ["First quarter", "التربيع الأول"],
  "waxing-gibbous": ["Waxing gibbous", "أحدب متزايد"], full: ["Full moon", "بدر"], "waning-gibbous": ["Waning gibbous", "أحدب متناقص"],
  "last-quarter": ["Last quarter", "التربيع الأخير"], "waning-crescent": ["Waning crescent", "هلال متناقص"],
};

function useCoords(ar: boolean) {
  const [coords, setCoords] = useState<Coords | null>(null);
  const [lat, setLat] = useState(""); const [lon, setLon] = useState("");
  useEffect(() => {
    if (!("geolocation" in navigator)) return;
    navigator.geolocation.getCurrentPosition((p) => setCoords({ latitude: p.coords.latitude, longitude: p.coords.longitude }), () => undefined);
  }, []);
  const form = (
    <p className="tool-note">
      {ar ? "أدخل موقعك لحساب أوقات السحور والإفطار: " : "Enter your location for suhoor and iftar times: "}
      <input aria-label="latitude" placeholder="21.4225" value={lat} onChange={(e) => setLat(e.target.value)} size={8} />{" "}
      <input aria-label="longitude" placeholder="39.8262" value={lon} onChange={(e) => setLon(e.target.value)} size={8} />{" "}
      <button type="button" onClick={() => { const a = Number(lat), b = Number(lon); if (Number.isFinite(a) && Number.isFinite(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180 && lat !== "" && lon !== "") setCoords({ latitude: a, longitude: b }); }}>{ar ? "استخدم" : "Use"}</button>
    </p>
  );
  return { coords, form };
}

function Ramadan({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const now = useMemo(() => new Date(), []);
  const { coords, form } = useCoords(ar);
  const h = hijriParts(now);
  const inRamadan = h.month === 9;
  const start = inRamadan ? gregorianOfHijri(h.year, 9, 1) : nextHijriEvent("ramadan", now);
  const eid = nextHijriEvent("eid-fitr", now);
  const year = start ? hijriParts(start).year : h.year;
  const storageKey = `woi-fasting-${year}`;
  const [fasted, setFasted] = useState<number[]>([]);
  useEffect(() => { setFasted(load<number[]>(storageKey, [])); }, [storageKey]);
  const toggle = (d: number) => setFasted((prev) => { const next = prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]; save(storageKey, next); return next; });
  const times = coords ? computeSalahTimes(now, coords.latitude, coords.longitude) : null;
  const t = (d: Date) => d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  const length = start && eid ? daysBetween(start, eid) : 30;
  return (
    <section className="tool-card" aria-labelledby="ramadan-h">
      <h2 id="ramadan-h">{ar ? "رمضان والصيام" : "Ramadan & fasting"}</h2>
      {start && (
        <p className="tool-value">
          {inRamadan
            ? (ar ? `اليوم ${h.day} من رمضان ${h.year}` : `Day ${h.day} of Ramadan ${h.year}`)
            : (ar ? `يبدأ رمضان ${year} هـ بعد ${daysBetween(now, start)} يوماً` : `Ramadan ${year} AH begins in ${daysBetween(now, start)} days`)}
        </p>
      )}
      {start && <p className="tool-note">{ar ? "التاريخ المتوقع: " : "Expected: "}{fmtDate(start, locale)} {ar ? "(تقويم أم القرى؛ قد يختلف يوماً حسب رؤية الهلال)" : "(Umm al-Qura calendar; may differ by a day with local moon sighting)"}</p>}
      {form}
      {times && <p className="tool-note">{ar ? "السحور ينتهي عند الفجر: " : "Suhoor ends at Fajr: "}<strong>{t(times.fajr)}</strong> · {ar ? "الإفطار عند المغرب: " : "Iftar at Maghrib: "}<strong>{t(times.maghrib)}</strong> ({ar ? "بتوقيت جهازك" : "in your device’s time zone"})</p>}
      <h3>{ar ? "سجل الصيام" : "Fasting log"}</h3>
      <div className="fast-grid" role="group" aria-label={ar ? "أيام الصيام" : "Fasting days"}>
        {Array.from({ length }, (_, i) => i + 1).map((d) => (
          <label key={d}><input type="checkbox" checked={fasted.includes(d)} onChange={() => toggle(d)} /> {d}</label>
        ))}
      </div>
      <p className="tool-note">{fasted.length}/{length} {ar ? "يوماً. يُحفظ على جهازك فقط." : "days. Saved on this device only."}</p>
    </section>
  );
}

function Moon({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const now = useMemo(() => new Date(), []);
  const phase = moonPhase(now);
  const nm = nextPhaseDate(now, 0); const fm = nextPhaseDate(now, 0.5);
  return (
    <section className="tool-card" aria-labelledby="moon-h">
      <h2 id="moon-h">{ar ? "القمر" : "Moon"}</h2>
      <p className="tool-value">{PHASES[phase][ar ? 1 : 0]} · {Math.round(moonIllumination(now) * 100)}%</p>
      <p className="tool-note">{ar ? "عمر القمر: " : "Moon age: "}{moonAgeDays(now).toFixed(1)} {ar ? "يوماً" : "days"}</p>
      <p className="tool-note">{ar ? "المحاق القادم تقريباً: " : "Next new moon (approx.): "}{fmtDate(nm, locale)} · {ar ? "البدر القادم: " : "next full moon: "}{fmtDate(fm, locale)}</p>
      <p className="tool-note">{ar ? "حساب تقريبي للعرض فقط، ولا يغني عن رؤية الهلال." : "An approximate calculation for display only. It is not a substitute for moon sighting."}</p>
    </section>
  );
}

function HajjDates({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const now = useMemo(() => new Date(), []);
  const items: [string, string, ReturnType<typeof nextHijriEvent>][] = [
    ["Day of Arafah (9 Dhul Hijjah)", "يوم عرفة (٩ ذو الحجة)", nextHijriEvent("arafah", now)],
    ["Eid al-Adha (10 Dhul Hijjah)", "عيد الأضحى (١٠ ذو الحجة)", nextHijriEvent("eid-adha", now)],
    ["Eid al-Fitr (1 Shawwal)", "عيد الفطر (١ شوال)", nextHijriEvent("eid-fitr", now)],
  ];
  return (
    <section className="tool-card" aria-labelledby="hajj-h">
      <h2 id="hajj-h">{ar ? "الحج والأعياد" : "Hajj & Eid dates"}</h2>
      <ul className="plain-list">
        {items.map(([en, arName, d]) => d && <li key={en}><strong>{ar ? arName : en}</strong>: {fmtDate(d, locale)} · {ar ? `بعد ${daysBetween(now, d)} يوماً` : `in ${daysBetween(now, d)} days`}</li>)}
      </ul>
      <p className="tool-note">{ar ? "تقويم أم القرى؛ قد يختلف يوماً حسب رؤية الهلال." : "Umm al-Qura calendar; may differ by a day with local moon sighting."}</p>
    </section>
  );
}

const PRAYERS: [string, string][] = [["Fajr", "الفجر"], ["Dhuhr", "الظهر"], ["Asr", "العصر"], ["Maghrib", "المغرب"], ["Isha", "العشاء"]];

function Worship({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [log, setLog] = useState<Record<string, number[]>>({});
  useEffect(() => { setLog(load("woi-prayer-log", {})); }, []);
  const today = dayKey(new Date());
  const toggle = (i: number) => setLog((prev) => {
    const cur = prev[today] ?? [];
    const next = { ...prev, [today]: cur.includes(i) ? cur.filter((x) => x !== i) : [...cur, i] };
    save("woi-prayer-log", next); return next;
  });
  const days = Array.from({ length: 7 }, (_, k) => { const d = new Date(); d.setDate(d.getDate() - (6 - k)); return dayKey(d); });
  let streak = 0;
  for (let k = 0; k < 365; k++) { const d = new Date(); d.setDate(d.getDate() - k); if ((log[dayKey(d)] ?? []).length === 5) streak++; else if (k > 0 || (log[today] ?? []).length > 0) break; }
  return (
    <section className="tool-card" aria-labelledby="worship-h">
      <h2 id="worship-h">{ar ? "متابعة العبادة" : "Worship tracker"}</h2>
      <div role="group" aria-label={ar ? "صلوات اليوم" : "Today's prayers"}>
        {PRAYERS.map(([en, arName], i) => <label key={en} className="governance-check"><input type="checkbox" checked={(log[today] ?? []).includes(i)} onChange={() => toggle(i)} /> {ar ? arName : en}</label>)}
      </div>
      <p className="tool-value">{ar ? `أيام متتالية بخمس صلوات: ${streak}` : `Day streak with all five prayers: ${streak}`}</p>
      <p className="tool-note">{ar ? "آخر ٧ أيام: " : "Last 7 days: "}{days.map((d) => (log[d] ?? []).length).join(" · ")} / 5</p>
      <p className="tool-note">{ar ? "يُحفظ على جهازك فقط ولا يُرسل إلى أي خادم." : "Saved on this device only, never sent to a server."}</p>
    </section>
  );
}

type Surah = { surah_number: number; arabic_name: string; transliterated_name: string; ayah_count: number };

function Hifz({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [surahs, setSurahs] = useState<Surah[] | null>(null);
  const [done, setDone] = useState<number[]>([]);
  useEffect(() => { setDone(load<number[]>("woi-hifz", [])); apiFetch<Surah[]>("/quran/surahs").then(setSurahs).catch(() => setSurahs([])); }, []);
  const toggle = (n: number) => setDone((prev) => { const next = prev.includes(n) ? prev.filter((x) => x !== n) : [...prev, n]; save("woi-hifz", next); return next; });
  const total = surahs?.reduce((a, s) => a + s.ayah_count, 0) ?? 0;
  const memorised = surahs?.filter((s) => done.includes(s.surah_number)).reduce((a, s) => a + s.ayah_count, 0) ?? 0;
  return (
    <section className="tool-card" aria-labelledby="hifz-h">
      <h2 id="hifz-h">{ar ? "متابعة الحفظ" : "Hifz tracker"}</h2>
      {surahs === null ? <p role="status">{ar ? "جارٍ التحميل…" : "Loading…"}</p>
        : surahs.length === 0 ? <p className="tool-note">{ar ? "تتطلب هذه الأداة نشر نص القرآن." : "This tool needs the Qur’an text to be published."}</p>
        : <>
          <p className="tool-value">{done.length}/114 {ar ? "سورة" : "surahs"} · {memorised}/{total} {ar ? "آية" : "ayahs"}</p>
          <div className="fast-grid" role="group" aria-label={ar ? "السور المحفوظة" : "Memorised surahs"}>
            {surahs.map((s) => <label key={s.surah_number} title={s.transliterated_name}><input type="checkbox" checked={done.includes(s.surah_number)} onChange={() => toggle(s.surah_number)} /> {s.surah_number}. {ar ? s.arabic_name : s.transliterated_name}</label>)}
          </div>
          <p className="tool-note">{ar ? "يُحفظ على جهازك فقط." : "Saved on this device only."}</p>
        </>}
    </section>
  );
}

export function IbadahPlanner({ locale }: { locale: Locale }) {
  return <div className="tools-grid"><Ramadan locale={locale} /><Worship locale={locale} /><Moon locale={locale} /><HajjDates locale={locale} /><Hifz locale={locale} /></div>;
}
