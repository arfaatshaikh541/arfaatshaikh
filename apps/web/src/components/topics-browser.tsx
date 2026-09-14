"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Topic = { id: string; key: string; english_name: string; arabic_name: string; parent_topic_id: string | null };
type CrossRef = {
  id: string; source_type: string; source_entity_id: string; target_type: string;
  target_entity_id: string; relationship_type: string; rationale: string; editorial_confidence: number;
};
type TopicDetail = { topic: { id: string; key: string; english_name: string; arabic_name: string; description: string | null }; references: CrossRef[] };

const ENTITY_LABEL: Record<string, { en: string; ar: string }> = {
  quran_ayah: { en: "Qur'an ayah", ar: "آية قرآنية" },
  hadith_narration: { en: "Hadith narration", ar: "رواية حديث" },
  tafsir_entry: { en: "Tafsir entry", ar: "مدخل تفسير" },
  topic: { en: "Topic", ar: "موضوع" },
};

export function TopicsBrowser({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [selected, setSelected] = useState<TopicDetail | null>(null);
  const [message, setMessage] = useState(ar ? "جارٍ تحميل المواضيع المنشورة…" : "Loading published topics…");
  const [detailMessage, setDetailMessage] = useState("");

  useEffect(() => {
    void apiFetch<Topic[]>("/tafsir/topics")
      .then((rows) => { setTopics(rows); setMessage(rows.length ? "" : (ar ? "لا توجد مواضيع منشورة بعد." : "No published topics yet.")); })
      .catch(() => setMessage(ar ? "تعذّر تحميل المواضيع." : "Topics could not be loaded."));
  }, [ar]);

  async function select(key: string) {
    setDetailMessage(ar ? "جارٍ التحميل…" : "Loading…");
    setSelected(null);
    try {
      const detail = await apiFetch<TopicDetail>(`/tafsir/topics/${encodeURIComponent(key)}`);
      setSelected(detail);
      setDetailMessage("");
    } catch {
      setDetailMessage(ar ? "تعذّر تحميل تفاصيل الموضوع." : "Topic details could not be loaded.");
    }
  }

  return (
    <div className="topics-browser">
      <aside className="topics-list-panel">
        <h2>{ar ? "المواضيع" : "Topics"}</h2>
        {topics === null || topics.length === 0 ? (
          <p role="status" className="tool-note">{message}</p>
        ) : (
          <ul className="topics-list">
            {topics.map((topic) => (
              <li key={topic.id}>
                <button type="button" onClick={() => select(topic.key)} className={selected?.topic.key === topic.key ? "topic-item topic-item-active" : "topic-item"}>
                  {ar ? topic.arabic_name : topic.english_name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <section className="topic-detail-panel" aria-live="polite">
        {!selected && !detailMessage && (
          <p className="tool-note">{ar ? "اختر موضوعًا لعرض الروابط المعرفية الحقيقية المرتبطة به." : "Select a topic to see its real, published cross-reference links."}</p>
        )}
        {detailMessage && <p role="status">{detailMessage}</p>}
        {selected && (
          <>
            <h2>{ar ? selected.topic.arabic_name : selected.topic.english_name}</h2>
            {selected.topic.description && <p>{selected.topic.description}</p>}
            {selected.references.length === 0 ? (
              <p className="tool-note">
                {ar
                  ? "لا توجد روابط معرفية منشورة لهذا الموضوع بعد. هذا انعكاس حقيقي لحالة البيانات - وليس عطلاً."
                  : "No published cross-references exist for this topic yet. This is a real reflection of the data, not a bug."}
              </p>
            ) : (
              <ul className="feature-list">
                {selected.references.map((ref) => (
                  <li key={ref.id} className="feature-item">
                    <div className="feature-list-head">
                      <h3>{ref.relationship_type}</h3>
                      <span className="status-pill status-backend-only">
                        {ENTITY_LABEL[ref.source_type]?.[ar ? "ar" : "en"] ?? ref.source_type} → {ENTITY_LABEL[ref.target_type]?.[ar ? "ar" : "en"] ?? ref.target_type}
                      </span>
                    </div>
                    <p>{ref.rationale}</p>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  );
}
