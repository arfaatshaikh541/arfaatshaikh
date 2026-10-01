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
