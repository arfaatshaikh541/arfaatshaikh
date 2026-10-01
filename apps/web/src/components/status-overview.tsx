"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { READINESS_LABEL } from "@/lib/copy";
import { allFeatures, featureCounts, STATUS_ORDER, type FeatureStatus } from "@/lib/worlds";

type Manifest = { as_of: string; datasets: { id: string; name: string; license: { name: string; status: string }; provenance: string; validation_status: string; readiness: string; public: boolean; remaining_action: string | null; source: { name: string; version: string | null } }[] };

const STATUS_TEXT: Record<FeatureStatus, { en: string; ar: string }> = {
  IMPLEMENTED: { en: "Implemented", ar: "مُنجز" }, PARTIALLY_IMPLEMENTED: { en: "Partly implemented", ar: "منجز جزئياً" }, NOT_VERIFIED: { en: "Not yet verified", ar: "لم يُتحقق منه" },
  DATA_SOURCE_REQUIRED: { en: "Data source required", ar: "يتطلب مصدر بيانات" }, ARCHITECTURE_READY: { en: "Ready for data", ar: "جاهز للبيانات" }, NOT_IMPLEMENTED: { en: "Not built", ar: "غير مبني" },
};

export function StatusOverview({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const counts = featureCounts();
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [filter, setFilter] = useState<FeatureStatus | "ALL">("ALL");
  useEffect(() => { apiFetch<Manifest>("/knowledge/manifest").then(setManifest).catch(() => undefined); }, []);
  const features = allFeatures().filter((f) => filter === "ALL" || f.status === filter);
  return (
    <main className="knowledge-page" dir={ar ? "rtl" : "ltr"}>
      <h1>{ar ? "الحالة الصادقة للمنصة" : "Honest platform status"}</h1>
      <p className="tool-note">{ar ? "ما هو منجز وما ينتظر بيانات أو ترخيصاً، دون ادعاء." : "What is built, and what is waiting for data or a licence, without overstating."}</p>
      <section aria-label={ar ? "ملخص القدرات" : "Capability summary"}>
        <div className="knowledge-types">
          <button className={filter === "ALL" ? "chip chip-active" : "chip"} onClick={() => setFilter("ALL")}>{ar ? "الكل" : "All"} ({counts.total})</button>
          {STATUS_ORDER.map((s) => <button key={s} className={filter === s ? "chip chip-active" : "chip"} onClick={() => setFilter(s)}>{STATUS_TEXT[s][ar ? "ar" : "en"]} ({counts.byStatus[s]})</button>)}
        </div>
        <ul className="feature-list">{features.map((f) => <li key={f.id} className="feature-item"><div className="feature-list-head"><h2>{f.name}</h2><span className={`status-pill status-${f.status.toLowerCase().replaceAll("_", "-")}`}>{STATUS_TEXT[f.status][ar ? "ar" : "en"]}</span></div><p>{f.note}</p></li>)}</ul>
      </section>
      <section aria-label={ar ? "المصادر" : "Sources"}>
        <h2>{ar ? "المصادر والتراخيص" : "Sources and licences"}</h2>
        {!manifest && <p aria-busy="true">…</p>}
        {manifest && (
          <table className="audit-table"><thead><tr><th>{ar ? "المصدر" : "Source"}</th><th>{ar ? "الترخيص" : "Licence"}</th><th>{ar ? "الحالة" : "Status"}</th><th>{ar ? "عام" : "Public"}</th></tr></thead>
            <tbody>{manifest.datasets.map((d) => <tr key={d.id}><td><strong>{d.name}</strong><br /><small>{d.source.name}{d.source.version ? ` ${d.source.version}` : ""}</small></td><td>{d.license.name}<br /><small>{d.license.status}</small></td><td>{READINESS_LABEL[d.readiness]?.[ar ? "ar" : "en"] ?? d.readiness}{d.remaining_action ? <><br /><small>{d.remaining_action}</small></> : null}</td><td>{d.public ? (ar ? "نعم" : "Yes") : (ar ? "لا" : "No")}</td></tr>)}</tbody></table>
        )}
      </section>
    </main>
  );
}
