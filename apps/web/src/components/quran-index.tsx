"use client";

import Link from "next/link";
import { NOT_PUBLIC } from "@/lib/copy";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Surah = { surah_number: number; arabic_name: string; transliterated_name: string; ayah_count: number; revelation_classification: string };

export function QuranIndex({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [surahs, setSurahs] = useState<Surah[] | null>(null);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    apiFetch<Surah[]>("/quran/surahs").then(setSurahs).catch(() => setError(true));
  }, []);

  if (error) return <p role="alert">{ar ? "تعذّر تحميل السور." : "The surah list could not be loaded."}</p>;
  if (!surahs) return <p role="status">{ar ? "جارٍ التحميل…" : "Loading…"}</p>;
  if (surahs.length === 0) return <p role="status">{NOT_PUBLIC[ar ? "ar" : "en"]}</p>;

  const q = filter.trim().toLowerCase();
  const shown = surahs.filter((s) => !q || String(s.surah_number) === q || s.transliterated_name.toLowerCase().includes(q) || s.arabic_name.includes(filter.trim()));
  return (
    <section aria-label={ar ? "فهرس السور" : "Surah index"}>
      <label className="sr-only" htmlFor="surah-filter">{ar ? "ابحث عن سورة" : "Find a surah"}</label>
      <input id="surah-filter" type="search" value={filter} onChange={(e) => setFilter(e.target.value)}
        placeholder={ar ? "ابحث عن سورة…" : "Find a surah by name or number…"} />
      <ol className="surah-list">
        {shown.map((s) => (
          <li key={s.surah_number}>
            <Link href={`/${locale}/quran/${s.surah_number}`}>
              <span>{s.surah_number}</span>
              <strong lang="ar" dir="rtl">{s.arabic_name}</strong>
              <em>{s.transliterated_name}</em>
              <small>{s.ayah_count} {ar ? "آيات" : "ayahs"} · {s.revelation_classification}</small>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
