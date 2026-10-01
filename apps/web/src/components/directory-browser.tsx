"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { LISTING_EMPTY, LISTING_TYPES } from "@/lib/copy";

export type Listing = { id: string; type: string; name: string; arabic_name: string | null; description: string | null; category: string | null; address: string | null; city: string | null; country: string | null;
  phone: string | null; email: string | null; website: string | null; source: string; source_url: string | null; license: string; verification_status: string; last_updated: string; distance_km: number | null;
  starts_at?: string | null; ends_at?: string | null; expires_at?: string | null; provenance?: string; attributes?: Record<string, unknown> };
type Result = { total: number; page: number; page_size: number; items: Listing[] };
type Summary = { types: { type: string; count: number }[] };
type Coverage = { countries_by_type: Record<string, string[]>; statement: string };

export function ListingCard({ item, locale }: { item: Listing; locale: "en" | "ar" }) {
  const ar = locale === "ar";
  return (
    <li className="record-card">
      <h2><Link href={`/${locale}/directory/${item.id}`}>{item.name}</Link>{item.arabic_name && <span lang="ar" dir="rtl" className="record-ar"> {item.arabic_name}</span>}</h2>
      <p className="tool-note">
        {[item.address, item.city, item.country].filter(Boolean).join(", ")}
        {item.distance_km !== null && ` · ${item.distance_km} km`}
      </p>
      {item.description && <p>{item.description}</p>}
      <ListingFacts item={item} ar={ar} />
      <p>
        <span className={item.verification_status === "verified" ? "status-pill status-implemented" : "status-pill status-architecture-ready"}>
          {item.verification_status === "verified" ? (ar ? "موثَّق" : "Verified") : (ar ? "غير موثَّق" : "Not verified")}
        </span>
        {" "}<small>{ar ? "المصدر" : "Source"}: {item.source_url ? <a href={item.source_url} rel="noopener noreferrer nofollow">{item.source}</a> : item.source} · {item.license} · {ar ? "آخر تحديث" : "Updated"} {item.last_updated}</small>
      </p>
    </li>
  );
}

function ListingFacts({ item, ar }: { item: Listing; ar: boolean }) {
  const a = item.attributes ?? {};
  const when = (value?: string | null) => (value ? new Date(value).toLocaleString(ar ? "ar" : "en", { dateStyle: "medium", timeStyle: "short" }) : null);
  return (
    <ul className="tool-note">
      {typeof a.employer === "string" && <li>{ar ? "جهة العمل" : "Employer"}: {a.employer}{typeof a.employment_type === "string" ? ` · ${a.employment_type.replace(/_/g, " ")}` : ""}</li>}
      {typeof a.organization === "string" && <li>{ar ? "الجهة" : "Organisation"}: {a.organization}</li>}
      {typeof a.organizer === "string" && <li>{ar ? "المنظّم" : "Organiser"}: {a.organizer}</li>}
      {item.starts_at && <li>{ar ? "يبدأ" : "Starts"}: {when(item.starts_at)}{item.ends_at ? ` · ${ar ? "ينتهي" : "ends"} ${when(item.ends_at)}` : ""}</li>}
      {item.expires_at && <li>{ar ? "آخر موعد" : "Closes"}: {when(item.expires_at)}</li>}
      {typeof a.application_url === "string" && <li><a href={a.application_url} rel="noopener noreferrer nofollow">{ar ? "التقديم" : "Apply"}</a></li>}
      {typeof a.denomination === "string" && <li>{ar ? "المذهب (كما ورد في المصدر)" : "Denomination (as stated by the source)"}: {a.denomination}{typeof a.denomination_source === "string" ? ` — ${a.denomination_source}` : ""}</li>}
    </ul>
  );
}

export function DirectoryBrowser({ locale, initialType }: { locale: "en" | "ar"; initialType?: string }) {
  const ar = locale === "ar";
  const [type, setType] = useState(initialType ?? "mosque");
  const [q, setQ] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [verified, setVerified] = useState(false);
  const [near, setNear] = useState<{ lat: number; lon: number } | null>(null);
  const [radius, setRadius] = useState(10);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Result | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { apiFetch<Summary>("/directory/summary").then(setSummary).catch(() => undefined); apiFetch<Coverage>("/directory/coverage").then(setCoverage).catch(() => undefined); }, []);
  useEffect(() => {
    const params = new URLSearchParams({ type, page: String(page) });
    if (q.trim()) params.set("q", q.trim());
    if (city.trim()) params.set("city", city.trim());
    if (country.trim().length === 2) params.set("country", country.trim().toUpperCase());
    if (verified) params.set("verified_only", "true");
    if (near) { params.set("lat", String(near.lat)); params.set("lon", String(near.lon)); params.set("radius_km", String(radius)); }
    setError("");
    apiFetch<Result>(`/directory/listings?${params}`).then(setData).catch(() => setError(ar ? "تعذّر تحميل الدليل." : "Could not load the directory."));
  }, [type, q, city, country, verified, near, radius, page, ar]);

  function locate() {
    if (!navigator.geolocation) { setError(ar ? "الموقع غير متاح في هذا المتصفح." : "Location is not available in this browser."); return; }
    navigator.geolocation.getCurrentPosition((p) => { setNear({ lat: p.coords.latitude, lon: p.coords.longitude }); setPage(1); }, () => setError(ar ? "تعذّر تحديد موقعك." : "Could not get your location."), { maximumAge: 600000 });
  }
  const count = (t: string) => summary?.types.find((x) => x.type === t)?.count;
  return (
    <main className="knowledge-page" dir={ar ? "rtl" : "ltr"}>
      <h1>{ar ? "الدليل" : "Directory"}</h1>
      <p className="tool-note">{ar ? "لا تُعرض هنا إلا قوائم لها مصدر وترخيص ومنشأ موثق. لا قوائم مختلقة." : "Only listings with a source, licence and provenance are shown. Nothing here is invented."}</p>
      <nav className="knowledge-types" aria-label={ar ? "أنواع القوائم" : "Listing types"}>
        {LISTING_TYPES.map((t) => <button key={t.id} className={t.id === type ? "chip chip-active" : "chip"} aria-pressed={t.id === type} onClick={() => { setType(t.id); setPage(1); }}>{ar ? t.ar : t.en}{count(t.id) !== undefined ? ` (${count(t.id)})` : ""}</button>)}
      </nav>
      <form role="search" className="filter-row" onSubmit={(e) => e.preventDefault()}>
        <label>{ar ? "بحث" : "Search"}<input type="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></label>
        <label>{ar ? "المدينة" : "City"}<input value={city} onChange={(e) => { setCity(e.target.value); setPage(1); }} /></label>
        <label>{ar ? "الدولة (رمزان)" : "Country (2-letter)"}<input value={country} maxLength={2} onChange={(e) => { setCountry(e.target.value); setPage(1); }} /></label>
        <label className="check"><input type="checkbox" checked={verified} onChange={(e) => { setVerified(e.target.checked); setPage(1); }} /> {ar ? "الموثَّق فقط" : "Verified only"}</label>
        <button type="button" onClick={locate}>{near ? (ar ? "تحديث موقعي" : "Update my location") : (ar ? "بالقرب مني" : "Near me")}</button>
        {near && <label>{ar ? "المسافة (كم)" : "Radius (km)"}<input type="number" min={1} max={500} value={radius} onChange={(e) => setRadius(Math.max(1, Number(e.target.value) || 1))} /></label>}
        {near && <button type="button" onClick={() => setNear(null)}>{ar ? "إلغاء الموقع" : "Clear location"}</button>}
      </form>
      {coverage && (
        <p className="tool-note" role="note" data-testid="coverage-note">
          {(coverage.countries_by_type[type] ?? []).length > 0
            ? `${ar ? "الدول التي لها بيانات لهذا النوع" : "Countries with data for this type"}: ${coverage.countries_by_type[type].join(", ")}. ${ar ? "لا تعني قلة القوائم في أي مكان آخر غياب الخدمات هناك." : "No data yet for any other country; a missing listing does not mean a missing place."}`
            : (ar ? "لا توجد بيانات لهذا النوع في أي دولة بعد." : "No country has data for this type yet.")}
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {data && data.items.length === 0 && !error && (
        <section className="empty-state" role="status">
          <h2>{LISTING_EMPTY[type]?.[ar ? "ar" : "en"] ?? (ar ? "لا توجد قوائم منشورة لهذا النوع بعد." : "No listings are published for this type yet.")}</h2>
          <p className="tool-note">{ar ? "تُضاف القوائم عبر مجموعات بيانات مرخّصة أو اقتراحات المجتمع بعد مراجعة المشرفين." : "Listings arrive through authorised datasets or community suggestions that moderators approve."}</p>
        </section>
      )}
      {type === "mosque" && data && data.items.length > 0 && (
        <p className="tool-note" role="note">
          {ar ? "بيانات المساجد: © مساهمو OpenStreetMap (رخصة ODbL) وWikidata (CC0)، عبر GeoAlgeria. بيانات مجتمعية وليست سجلاً رسمياً، وقد تحتوي أخطاء." : "Mosque data: © OpenStreetMap contributors (ODbL) and Wikidata (CC0), via GeoAlgeria. Community-sourced, not an official registry, and may contain errors."}
          {" "}<a href="https://www.openstreetmap.org/copyright" rel="noopener noreferrer nofollow">{ar ? "حقوق النشر" : "Copyright"}</a>
        </p>
      )}
      <ul className="record-list">{data?.items.map((item) => <ListingCard key={item.id} item={item} locale={locale} />)}</ul>
      {data && data.total > data.page_size && (
        <div className="pager"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>{ar ? "السابق" : "Previous"}</button><span>{page} / {Math.ceil(data.total / data.page_size)}</span><button disabled={page * data.page_size >= data.total} onClick={() => setPage(page + 1)}>{ar ? "التالي" : "Next"}</button></div>
      )}
      <SuggestListing locale={locale} />
    </main>
  );
}

function SuggestListing({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {
      listing_type: f.get("listing_type"), name: f.get("name"), city: f.get("city") || null, country: (f.get("country") as string)?.toUpperCase() || null, address: f.get("address") || null,
      website: f.get("website") || null, description: f.get("description") || null,
      source: "Community suggestion", license: "Contributor grant (see terms)", provenance: String(f.get("provenance") || "Suggested by a signed-in user"),
    };
    try {
      const r = await apiFetch<{ message: string }>("/directory/listings", { method: "POST", body: JSON.stringify(body) });
      setMsg(r.message); (e.target as HTMLFormElement).reset();
    } catch (err) { setMsg(err instanceof ApiError && err.status === 401 ? (ar ? "سجّل الدخول لاقتراح قائمة." : "Sign in to suggest a listing.") : (err instanceof ApiError ? err.message : ar ? "تعذّر الإرسال." : "Could not submit.")); }
  }
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)} className="suggest">
      <summary>{ar ? "اقترح قائمة" : "Suggest a listing"}</summary>
      <form onSubmit={submit} className="stack">
        <label>{ar ? "النوع" : "Type"}<select name="listing_type">{LISTING_TYPES.map((t) => <option key={t.id} value={t.id}>{ar ? t.ar : t.en}</option>)}</select></label>
        <label>{ar ? "الاسم" : "Name"}<input name="name" required minLength={2} maxLength={300} /></label>
        <label>{ar ? "العنوان" : "Address"}<input name="address" maxLength={500} /></label>
        <label>{ar ? "المدينة" : "City"}<input name="city" maxLength={120} /></label>
        <label>{ar ? "الدولة (رمزان)" : "Country (2-letter code)"}<input name="country" maxLength={2} minLength={2} /></label>
        <label>{ar ? "الموقع الإلكتروني" : "Website"}<input name="website" type="url" /></label>
        <label>{ar ? "وصف" : "Description"}<textarea name="description" maxLength={5000} /></label>
        <label>{ar ? "كيف تعرف هذه المعلومات؟" : "How do you know this?"}<input name="provenance" required minLength={3} maxLength={500} /></label>
        <button>{ar ? "إرسال للمراجعة" : "Submit for review"}</button>
        {msg && <p role="status">{msg}</p>}
      </form>
    </details>
  );
}
