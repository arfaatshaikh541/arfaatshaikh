// Shared wording so every empty state says the same honest thing.
export const NOT_PUBLIC = {
  en: "Source not currently available for public publication.",
  ar: "المصدر غير متاح حالياً للنشر العام.",
};
export const INSUFFICIENT = { en: "Insufficient verified sources.", ar: "لا توجد مصادر موثقة كافية." };

export const READINESS_LABEL: Record<string, { en: string; ar: string }> = {
  VERIFIED: { en: "Verified", ar: "موثَّق" },
  NEEDS_REVIEW: { en: "Needs review", ar: "يحتاج مراجعة" },
  LICENSE_REQUIRED: { en: "Awaiting rights confirmation", ar: "بانتظار تأكيد الحقوق" },
  PROVENANCE_UNCLEAR: { en: "Provenance unclear", ar: "المصدر الأصلي غير واضح" },
  UNAVAILABLE: { en: "Source not reachable", ar: "المصدر غير متاح" },
  OWNER_UPLOAD_REQUIRED: { en: "Awaiting an authorised dataset", ar: "بانتظار مجموعة بيانات مرخّصة" },
};

export const KNOWLEDGE_TYPES = [
  { id: "fiqh", en: "Fiqh", ar: "الفقه" },
  { id: "aqeedah", en: "Aqeedah", ar: "العقيدة" },
  { id: "seerah", en: "Seerah", ar: "السيرة" },
  { id: "hadith_grading", en: "Hadith grading", ar: "درجات الحديث" },
  { id: "terminology", en: "Terminology", ar: "المصطلحات" },
  { id: "library_work", en: "Library", ar: "المكتبة" },
  { id: "history", en: "History", ar: "التاريخ" },
  { id: "civilization", en: "Civilization", ar: "الحضارة" },
  { id: "scholar", en: "Scholars", ar: "العلماء" },
  { id: "book", en: "Books", ar: "الكتب" },
  { id: "person", en: "People", ar: "الأعلام" },
  { id: "event", en: "Events", ar: "الأحداث" },
  { id: "place", en: "Places", ar: "الأماكن" },
  { id: "concept", en: "Concepts", ar: "المفاهيم" },
  { id: "institution", en: "Institutions", ar: "المؤسسات" },
] as const;

export const LISTING_TYPES = [
  { id: "mosque", en: "Mosques", ar: "المساجد" },
  { id: "business", en: "Businesses", ar: "الأعمال" },
  { id: "charity", en: "Charities", ar: "الجمعيات الخيرية" },
  { id: "job", en: "Jobs", ar: "الوظائف" },
  { id: "professional", en: "Professionals", ar: "المهنيون" },
  { id: "organisation", en: "Organisations", ar: "المنظمات" },
  { id: "event", en: "Events", ar: "الفعاليات" },
  { id: "volunteering", en: "Volunteering", ar: "التطوع" },
  { id: "health", en: "Health", ar: "الصحة" },
] as const;

export const SEARCH_TYPES = [
  { id: "quran", en: "Qur'an", ar: "القرآن" },
  { id: "hadith", en: "Hadith", ar: "الحديث" },
  { id: "tafsir", en: "Tafsir", ar: "التفسير" },
  { id: "topic", en: "Topics", ar: "المواضيع" },
  { id: "course", en: "Courses", ar: "الدورات" },
  { id: "directory", en: "Directory", ar: "الدليل" },
  ...KNOWLEDGE_TYPES.map((t) => ({ id: t.id, en: t.en, ar: t.ar })),
] as const;

// Honest empty states, shown only while a domain has no verified, publishable records.
export const KNOWLEDGE_EMPTY: Record<string, { en: string; ar: string }> = {
  fiqh: { en: "Verified Fiqh sources have not yet been imported.", ar: "لم تُستورد بعدُ مصادر فقهية موثّقة." },
  aqeedah: { en: "Verified Aqeedah sources have not yet been imported.", ar: "لم تُستورد بعدُ مصادر عقدية موثّقة." },
  seerah: { en: "Verified Seerah sources have not yet been imported.", ar: "لم تُستورد بعدُ مصادر موثّقة للسيرة النبوية." },
  hadith_grading: { en: "Verified hadith gradings have not yet been imported.", ar: "لم تُستورد بعدُ درجات حديثية موثّقة." },
  terminology: { en: "Verified terminology sources have not yet been imported.", ar: "لم تُستورد بعدُ مصادر موثّقة للمصطلحات." },
  library_work: { en: "Verified library records have not yet been imported.", ar: "لم تُستورد بعدُ سجلات موثّقة للمكتبة." },
  history: { en: "Verified history sources have not yet been imported.", ar: "لم تُستورد بعدُ مصادر موثّقة للتاريخ." },
  civilization: { en: "Verified civilization sources have not yet been imported.", ar: "لم تُستورد بعدُ مصادر موثّقة للحضارة." },
  scholar: { en: "Verified scholar biographies have not yet been imported.", ar: "لم تُستورد بعدُ تراجم موثّقة للعلماء." },
};
export const LISTING_EMPTY: Record<string, { en: string; ar: string }> = {
  mosque: { en: "No verified mosque data is currently available for this region.", ar: "لا تتوفر حاليًا بيانات موثّقة للمساجد في هذه المنطقة." },
  business: { en: "No verified business listings are currently available.", ar: "لا تتوفر حاليًا قوائم موثّقة للأعمال." },
  charity: { en: "No verified charity listings are currently available.", ar: "لا تتوفر حاليًا قوائم موثّقة للجمعيات الخيرية." },
  job: { en: "No verified job listings are currently available.", ar: "لا تتوفر حاليًا وظائف موثّقة." },
  professional: { en: "No verified professional listings are currently available.", ar: "لا تتوفر حاليًا قوائم موثّقة للمهنيين." },
  organisation: { en: "No verified organisation listings are currently available.", ar: "لا تتوفر حاليًا قوائم موثّقة للمنظمات." },
  event: { en: "No upcoming verified events are currently available.", ar: "لا تتوفر حاليًا فعاليات قادمة موثّقة." },
  volunteering: { en: "No verified volunteering opportunities are currently available.", ar: "لا تتوفر حاليًا فرص تطوع موثّقة." },
  health: { en: "No verified health listings are currently available.", ar: "لا تتوفر حاليًا قوائم موثّقة للخدمات الصحية." },
};
export const AUDIO_NOT_AVAILABLE = { en: "Recitation audio is not currently available for redistribution.", ar: "التلاوات الصوتية غير متاحة حاليًا لإعادة النشر." };

// How much weight a cited item deserves. The Arabic labels are NOT yet reviewed by a native speaker (see docs/ARABIC_QA.md).
export const AUTHORITY_LABEL: Record<string, { en: string; ar: string }> = {
  primary_source: { en: "Primary source", ar: "مصدر أصلي" },
  secondary_source: { en: "Secondary source", ar: "مصدر ثانوي" },
  community_dataset: { en: "Community dataset", ar: "مجموعة بيانات مجتمعية" },
  unverified: { en: "Unverified", ar: "غير موثَّق" },
  disputed: { en: "Disputed", ar: "محل خلاف" },
  inferred: { en: "Inferred", ar: "مستنتَج" },
  unavailable: { en: "No sufficiently reliable source is available", ar: "لا يتوفر مصدر موثوق كافٍ" },
};

// Domain readiness statuses. English is the source of truth; the Arabic is NOT yet reviewed by a native speaker (docs/ARABIC_QA.md).
export const DOMAIN_STATUS_LABEL: Record<string, { en: string; ar: string }> = {
  EMPTY: { en: "Empty: no data", ar: "فارغ: لا توجد بيانات" },
  SOURCE_BLOCKED: { en: "Source blocked", ar: "المصدر غير متاح" },
  SOURCE_UNVERIFIED: { en: "Source unverified", ar: "المصدر غير مؤكَّد" },
  RIGHTS_UNVERIFIED: { en: "Rights unverified", ar: "الحقوق غير مؤكَّدة" },
  IMPORT_READY: { en: "Ready to import", ar: "جاهز للاستيراد" },
  IMPORTED: { en: "Imported (hidden)", ar: "مستورد (مخفي)" },
  VALIDATED: { en: "Validated (not published)", ar: "تم التحقق (غير منشور)" },
  PUBLISHED: { en: "Published, gates open", ar: "منشور مع بنود غير مستوفاة" },
  READY: { en: "Ready", ar: "جاهز" },
};
export const COVERAGE_LABEL: Record<string, { en: string; ar: string }> = {
  NONE: { en: "No coverage", ar: "بلا تغطية" }, PARTIAL: { en: "Partial coverage", ar: "تغطية جزئية" }, FULL: { en: "Full coverage of the stated scope", ar: "تغطية كاملة للنطاق المذكور" },
};
