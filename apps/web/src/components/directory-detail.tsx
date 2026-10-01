"use client";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { ListingCard, type Listing } from "@/components/directory-browser";

export function DirectoryDetail({ locale, id }: { locale: "en" | "ar"; id: string }) {
  const ar = locale === "ar";
  const [item, setItem] = useState<Listing | null>(null);
  const [missing, setMissing] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { apiFetch<Listing>(`/directory/listings/${id}`).then(setItem).catch((e) => e instanceof ApiError && e.status === 404 && setMissing(true)); }, [id]);
  async function report(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try { await apiFetch(`/directory/listings/${id}/report`, { method: "POST", body: JSON.stringify({ reason: f.get("reason"), details: f.get("details") || null }) }); setMsg(ar ? "شكراً. سيراجع المشرفون البلاغ." : "Thank you. A moderator will review your report."); }
    catch (err) { setMsg(err instanceof ApiError && err.status === 401 ? (ar ? "سجّل الدخول للإبلاغ." : "Sign in to report a listing.") : ar ? "تعذّر الإرسال." : "Could not submit."); }
  }
  if (missing) return <main className="knowledge-page"><p role="status">{ar ? "هذه القائمة غير متاحة." : "This listing is not available."}</p></main>;
  if (!item) return <main className="knowledge-page"><p aria-busy="true">…</p></main>;
  return (
    <main className="knowledge-page" dir={ar ? "rtl" : "ltr"}>
      <ul className="record-list"><ListingCard item={item} locale={locale} /></ul>
      <dl className="provenance">
        {item.phone && <div><dt>{ar ? "الهاتف" : "Phone"}</dt><dd>{item.phone}</dd></div>}
        {item.email && <div><dt>Email</dt><dd>{item.email}</dd></div>}
        {item.website && <div><dt>{ar ? "الموقع" : "Website"}</dt><dd><a href={item.website} rel="noopener noreferrer nofollow">{item.website}</a></dd></div>}
      </dl>
      <details><summary>{ar ? "الإبلاغ عن مشكلة" : "Report a problem"}</summary>
        <form onSubmit={report} className="stack">
          <label>{ar ? "السبب" : "Reason"}<select name="reason"><option value="incorrect">{ar ? "معلومات غير صحيحة" : "Incorrect information"}</option><option value="closed">{ar ? "مغلق" : "Closed"}</option><option value="duplicate">{ar ? "مكرر" : "Duplicate"}</option><option value="offensive">{ar ? "مسيء" : "Offensive"}</option><option value="fraud">{ar ? "احتيال" : "Fraud"}</option><option value="other">{ar ? "آخر" : "Other"}</option></select></label>
          <label>{ar ? "تفاصيل" : "Details"}<textarea name="details" maxLength={2000} /></label>
          <button>{ar ? "إرسال البلاغ" : "Send report"}</button>
          {msg && <p role="status">{msg}</p>}
        </form>
      </details>
    </main>
  );
}
