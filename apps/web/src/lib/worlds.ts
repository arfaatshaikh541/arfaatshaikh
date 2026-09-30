// The 85-capability -> 12-world information architecture.
//
// `status` is load-bearing, not decorative:
//   - "available"     a real page exists and is backed by real API data.
//                      `href` must point at a route that actually works.
//   - "backend-only"   the milestone 1-20 backend already implements real
//                      logic/data for this (see docs/architecture/ARCHITECTURE.md)
//                      but no user-facing page has been built yet.
//   - "planned"        no real data source exists yet; architecture slot only.
//
// Never flip an item to "available" without a real route serving real data -
// that is exactly the fabrication this registry exists to prevent.

export type FeatureStatus = "available" | "backend-only" | "planned";

export interface Feature {
  id: string;
  name: string;
  status: FeatureStatus;
  href?: string;
  note: string;
  /** True only for a real, verified "available" capability that has no
   * dedicated page to link to (e.g. background infrastructure like the
   * offline service worker) - never used to excuse a missing destination
   * for something that should otherwise be clickable. */
  pageless?: true;
}

export interface World {
  slug: string;
  name: string;
  nameAr: string;
  tagline: string;
  taglineAr: string;
  features: Feature[];
}

const f = (id: string, name: string, status: FeatureStatus, note: string, href?: string): Feature => ({
  id, name, status, note, href,
});

export const worlds: World[] = [
  {
    slug: "ibadah",
    name: "Ibadah",
    nameAr: "العبادة",
    tagline: "Worship, kept accurate.",
    taglineAr: "العبادة، بدقة.",
    features: [
      f("quran", "Qur'an", "available", "Canonical Arabic text with reviewed translations, reading progress, and bookmarks.", "/quran"),
      f("quran-recitation", "Qur'an Recitation", "available", "Reciter selection and ayah-level audio playback inside the Qur'an reader.", "/quran"),
      f("salah", "Salah", "available", "Prayer times computed on-device from your location using standard astronomical formulas.", "/w/ibadah/tools"),
      f("salah-times", "Salah times", "available", "Same calculator as Salah - Fajr through Isha for a chosen calculation convention.", "/w/ibadah/tools"),
      f("qiblah", "Qiblah", "available", "Great-circle bearing to the Kaaba computed from your device location.", "/w/ibadah/tools"),
      f("dua", "Dua", "available", "Hisn al-Muslim, the Arabic supplications grouped by occasion. Each entry says how its Arabic was checked.", "/hadith/hisn/1/1"),
      f("dhikr", "Dhikr", "available", "Morning and evening adhkar with English and the source of each.", "/hadith/adhkar/1/1"),
      f("dhikr-counter", "Dhikr Counter", "available", "A private, on-device tally counter - no account or server data required.", "/w/ibadah/tools"),
      f("fasting", "Fasting", "available", "Fasting log for Ramadan with suhoor and iftar times from your location.", "/w/ibadah/planner"),
      f("ramadan", "Ramadan", "available", "Ramadan start date, countdown, and daily suhoor and iftar times.", "/w/ibadah/planner"),
      f("zakat", "Zakat", "available", "Checks a zakat fund's configuration against acceptance rules. Not a fund management system — no real funds are held here.", "/w/charity/zakat-checker"),
      f("zakat-calculator", "Zakat calculator", "available", "Estimate the zakat due on your wealth from the nisab you enter. Calculated on your device.", "/w/charity/zakat-calculator"),
      f("sadaqah", "Sadaqah", "backend-only", "Not built yet."),
      f("hajj", "Hajj", "available", "Day of Arafah and Eid dates with a countdown. Step-by-step guidance is not built yet.", "/w/ibadah/planner"),
      f("umrah", "Umrah", "planned", "Not built yet."),
      f("islamic-calendar", "Islamic Calendar", "available", "Hijri date shown via the platform's standard calendar conversion (an approximation - local moon-sighting authorities may differ by a day).", "/w/ibadah/tools"),
      f("moon", "Moon", "available", "Moon phase, age, and the next new and full moon (approximate).", "/w/ibadah/planner"),
      f("janazah", "Janazah", "planned", "Not built yet."),
      f("islamic-will", "Islamic Will", "planned", "Not built yet."),
      f("hifz", "Hifz", "available", "Mark memorised surahs and see your progress. Saved on your device.", "/w/ibadah/planner"),
      f("tajweed", "Tajweed", "available", "Tajweed colour-coding in the Qur'an reader, from a scholar-authored rule corpus.", "/quran/1"),
      f("worship-tracking", "Worship tracking", "available", "Daily prayer checklist with a streak. Saved on your device.", "/w/ibadah/planner"),
      f("offline-quran", "Offline Qur'an", "planned", "Downloading the Qur'an for offline reading isn't available yet."),
      { ...f("offline-app-shell", "Offline app shell", "available", "Pages you've visited keep working without a connection; Qur'an, Hadith, and Tafsir text is not cached yet."), pageless: true },
    ],
  },
  {
    slug: "knowledge",
    name: "Knowledge",
    nameAr: "المعرفة",
    tagline: "Text before commentary. Commentary before opinion.",
    taglineAr: "النص قبل الشرح، والشرح قبل الرأي.",
    features: [
      f("quran-k", "Qur'an", "available", "See Ibadah - the reader lives in one place.", "/quran"),
      f("tafsir", "Tafsir", "available", "Tafsir al-Jalalayn and Ibn Kathir (Arabic), with the English Jalalayn, ayah by ayah and attributed apart from the Qur'anic text.", "/tafsir/1/1"),
      f("hadith", "Hadith", "available", "Collection -> book -> chapter -> narration, with isnad and bookmarks.", "/hadith"),
      f("fiqh", "Fiqh", "planned", "Not built yet."),
      f("aqeedah", "Aqeedah", "planned", "Not built yet."),
      f("seerah", "Seerah", "planned", "Not built yet."),
      f("arabic", "Arabic", "planned", "See Education world for the Arabic-learning slot."),
      f("translation", "Translation", "backend-only", "Available today inside the Qur'an and Tafsir readers; a dedicated translation browser is not built yet."),
      f("terminology", "Islamic terminology", "planned", "Not built yet."),
      f("cross-references", "Cross references", "available", "Real, published cross-references between Qur'an ayat, Hadith narrations, Tafsir entries, and topics.", "/topics"),
      f("commentary", "Scholarly commentary", "available", "See Tafsir.", "/tafsir/1/1"),
      f("library", "Islamic Library", "planned", "No licensed book corpus has been imported."),
    ],
  },
  {
    slug: "scholarship",
    name: "Scholarship",
    nameAr: "العلم الشرعي",
    tagline: "Qur'an. Hadith. Classical scholarship. Contemporary scholarship. AI synthesis. Never blurred together.",
    taglineAr: "القرآن، الحديث، العلم الكلاسيكي، العلم المعاصر، وتوليف الذكاء الاصطناعي - كل منها منفصل وواضح.",
    features: [
      f("scholars", "Scholars", "backend-only", "Not built yet - a public directory will only publish scholars with verified biographical sourcing."),
      f("scholarly-works", "Scholarly works", "planned", "Not built yet."),
      f("fatwa-references", "Fatwa references", "planned", "Not built yet."),
      f("research", "Research", "available", "Research workspace for source-linked notes.", "/w/scholarship"),
      f("source-explorer", "Source explorer", "available", "Every source's registry status, licence, and review state - what backs the whole platform's evidence claims.", "/source-registry"),
      f("evidence", "Evidence", "available", "The assistant's retrieval pipeline exposes exact cited text, never paraphrase.", "/assistant"),
      f("citations", "Citations", "available", "Every assistant answer cites its evidence inline; nothing is asserted without one.", "/assistant"),
      f("hadith-grading", "Hadith grading", "planned", "No grading dataset has been imported."),
      f("narrator-info", "Narrator information", "available", "The Hadith reader shows isnad (chain) data where imported.", "/hadith"),
      f("schools-of-fiqh", "Schools of fiqh", "planned", "Not built yet."),
      f("scholarly-differences", "Scholarly differences", "planned", "Not built yet — will always present differing scholarly views side by side, never flattened into one answer."),
      f("primary-sources", "Primary-source references", "available", "See Source explorer.", "/source-registry"),
      f("source-verification", "Source verification", "available", "See Source explorer.", "/source-registry"),
      f("research-notes", "Research notes", "backend-only", "Not built yet."),
    ],
  },
  {
    slug: "civilization",
    name: "Civilization",
    nameAr: "الحضارة",
    tagline: "The intellectual history, not the mythology.",
    taglineAr: "التاريخ الفكري، لا الأساطير.",
    features: [
      f("history", "Islamic History", "planned", "No historical-timeline dataset has been imported."),
      f("civilization-timeline", "Islamic Civilization", "backend-only", "Not built yet."),
      f("timelines", "Historical timelines", "planned", "Not built yet."),
      f("maps", "Historical maps", "planned", "See The World for the live-map slot."),
      f("dynasties", "Dynasties", "planned", "Not built yet."),
      f("scholars-c", "Scholars", "backend-only", "See Scholarship world."),
      f("scientists", "Scientists", "planned", "Not built yet."),
      f("cities", "Cities", "planned", "See The World."),
      f("institutions", "Institutions", "backend-only", "Not built yet."),
      f("manuscripts", "Manuscripts", "backend-only", "Not built yet."),
      f("architecture", "Architecture", "planned", "Not built yet."),
      f("art", "Art", "planned", "Not built yet."),
      f("calligraphy", "Calligraphy", "planned", "Not built yet."),
      f("science", "Science", "planned", "Not built yet."),
      f("medicine", "Medicine", "planned", "Not built yet."),
      f("astronomy", "Astronomy", "available", "See Ibadah tools - the Qibla/prayer-time calculators use real solar-position astronomy.", "/w/ibadah/tools"),
      f("mathematics", "Mathematics", "planned", "Not built yet."),
      f("philosophy", "Philosophy", "planned", "Not built yet."),
      f("libraries", "Libraries", "planned", "See Islamic Library in Knowledge."),
    ],
  },
  {
    slug: "family",
    name: "Family",
    nameAr: "الأسرة",
    tagline: "Sensitive subjects, sourced responsibly.",
    taglineAr: "مواضيع حساسة، بمصادر موثوقة.",
    features: [
      f("muslim-women", "Muslim Women", "planned", "Not built yet — requires careful, reviewed sourcing before publishing."),
      f("muslim-men", "Muslim Men", "planned", "Not built yet."),
      f("marriage", "Marriage", "planned", "Not built yet."),
      f("nikah", "Nikah", "planned", "Not built yet."),
      f("family", "Family", "backend-only", "Not built yet."),
      f("parenting", "Parenting", "planned", "Not built yet."),
      f("children", "Children", "planned", "Not built yet."),
      f("inheritance", "Inheritance", "planned", "Not built yet — requires reviewed fiqh sourcing before publishing."),
      f("family-education", "Family education", "planned", "Not built yet."),
      f("family-rights", "Family rights", "planned", "Not built yet."),
      f("relationship-guidance", "Relationship guidance", "planned", "Not built yet."),
      f("childrens-education", "Children's Islamic education", "planned", "See Education world."),
    ],
  },
  {
    slug: "life",
    name: "Life",
    nameAr: "الحياة",
    tagline: "Where scholarship meets the marketplace - carefully.",
    taglineAr: "حيث يلتقي العلم بالسوق - بعناية.",
    features: [
      f("islamic-finance", "Islamic Finance", "backend-only", "Not built yet - will be educational only, never financial advice."),
      f("halal-investment", "Halal Investment Screening", "planned", "Not built yet — requires a licensed screening methodology before publishing."),
      f("halal-world", "Halal World", "backend-only", "Not built yet."),
      f("ingredient-checker", "Ingredient Checker", "planned", "Not built yet — will never claim halal/haram status from image recognition alone."),
      f("halal-certification", "Halal Certification", "backend-only", "See Halal World backend."),
      f("business-directory", "Muslim Business Directory", "planned", "Not built yet."),
      f("professional-network", "Muslim Professional Network", "planned", "Not built yet."),
      f("jobs", "Muslim Jobs", "planned", "Not built yet."),
      f("travel", "Muslim Travel", "planned", "See Journey world."),
      f("marketplace", "Islamic Marketplace", "planned", "Not built yet."),
      f("work", "Work", "planned", "Not built yet."),
      f("entrepreneurship", "Entrepreneurship", "planned", "Not built yet."),
    ],
  },
  {
    slug: "ummah",
    name: "Ummah",
    nameAr: "الأمة",
    tagline: "Community, with moderation and privacy designed in from the start.",
    taglineAr: "مجتمع مبني على الإشراف والخصوصية منذ التصميم.",
    features: [
      f("mosque-directory", "Mosque Directory", "planned", "Not built yet — requires a licensed/verified geodata source."),
      f("social-community", "Social Community", "backend-only", "Not built yet."),
      f("ummah-net", "Ummah", "backend-only", "Not built yet."),
      f("organizations", "Muslim organizations", "available", "Organisation workspaces (tenant-scoped) are live today.", "/organisations"),
      f("communities", "Communities", "backend-only", "See Social Community."),
      f("events", "Events", "backend-only", "Not built yet."),
      f("volunteering", "Volunteering", "planned", "Not built yet."),
      f("businesses", "Muslim businesses", "planned", "See Life world."),
      f("professionals", "Muslim professionals", "planned", "See Life world."),
      f("emergency-network", "Emergency network", "planned", "Not built yet."),
      f("institutions-u", "Institutions", "backend-only", "See Civilization world."),
      f("global-network", "Global Muslim network", "backend-only", "See Ummah net."),
    ],
  },
  {
    slug: "charity",
    name: "Charity",
    nameAr: "الصدقة",
    tagline: "Every campaign and every figure here is real.",
    taglineAr: "كل حملة وكل رقم هنا حقيقي.",
    features: [
      f("zakat-c", "Zakat", "available", "See Ibadah world - the same checker.", "/w/charity/zakat-checker"),
      f("zakat-calculator-c", "Zakat calculator", "available", "See Ibadah world - the same calculator.", "/w/charity/zakat-calculator"),
      f("sadaqah-c", "Sadaqah", "backend-only", "See Ibadah world."),
      f("waqf", "Waqf", "backend-only", "Not built yet."),
      f("humanitarian-aid", "Humanitarian aid", "planned", "Not built yet."),
      f("verified-orgs", "Verified organizations", "planned", "Not built yet — will only ever list organizations with a real, checkable verification record."),
      f("campaigns", "Campaigns", "planned", "Not built yet."),
      f("donation-opportunities", "Donation opportunities", "planned", "Not built yet."),
      f("charity-discovery", "Charity discovery", "planned", "Not built yet."),
      f("charitable-projects", "Charitable projects", "planned", "Not built yet."),
    ],
  },
  {
    slug: "journey",
    name: "Journey",
    nameAr: "الرحلة",
    tagline: "Pilgrimage, time, and place.",
    taglineAr: "الحج والزمان والمكان.",
    features: [
      f("hajj-j", "Hajj", "available", "See Ibadah world - Hajj and Eid dates.", "/w/ibadah/planner"),
      f("umrah-j", "Umrah", "planned", "See Ibadah world."),
      f("qiblah-j", "Qiblah", "available", "See Ibadah tools.", "/w/ibadah/tools"),
      f("islamic-calendar-j", "Islamic Calendar", "available", "See Ibadah tools.", "/w/ibadah/tools"),
      f("moon-j", "Moon", "available", "See Ibadah world - moon phase and dates.", "/w/ibadah/planner"),
      f("astronomy-j", "Islamic Astronomy", "available", "See Ibadah tools.", "/w/ibadah/tools"),
      f("travel-j", "Muslim Travel", "planned", "Not built yet."),
      f("mosque-discovery", "Mosque discovery", "planned", "See Ummah world."),
      f("hajj-prep", "Pilgrimage preparation", "planned", "Not built yet."),
      f("hajj-education", "Hajj education", "planned", "Not built yet."),
      f("umrah-education", "Umrah education", "planned", "Not built yet."),
      f("historical-sites", "Islamic historical sites", "planned", "See The World."),
    ],
  },
  {
    slug: "intelligence",
    name: "Intelligence",
    nameAr: "الذكاء",
    tagline: "Retrieval, not invention. It never claims to be a scholar.",
    taglineAr: "استرجاع، لا اختلاق - ولا يدّعي أبداً أنه عالم شرعي.",
    features: [
      f("ai-assistant", "Islamic AI Scholar / Assistant", "available", "Answers are composed only from approved, cited sources, with every quote linked back to its evidence.", "/assistant"),
      f("islamic-search", "Islamic Search", "available", "Full-text search over approved Qur'an, Hadith, and Tafsir text - not AI-generated.", "/search"),
      f("quran-search", "Qur'an Search", "available", "Filter Islamic Search to the Qur'an corpus.", "/search"),
      f("hadith-search", "Hadith Search", "available", "Filter Islamic Search to the Hadith corpus.", "/search"),
      f("tafsir-search", "Tafsir Search", "available", "Filter Islamic Search to the Tafsir corpus.", "/search"),
      f("fiqh-research", "Fiqh Research", "planned", "Depends on the Fiqh knowledge base in Knowledge world."),
      f("fact-checker", "Fact Checker", "available", "Exact-text check of Arabic passages against the published Qur'an and Hadith.", "/verify"),
      f("quran-verification", "Qur'an Verification", "available", "Check whether Arabic text appears word for word in the published Qur'an.", "/verify"),
      f("hadith-verification", "Hadith Verification", "available", "Check whether Arabic text appears word for word in the published Hadith collections. It does not grade authenticity.", "/verify"),
      f("source-explorer-i", "Source Explorer", "available", "See Scholarship world.", "/source-registry"),
      f("personal-assistant", "Personal Assistant", "planned", "Not built yet."),
      f("knowledge-graph", "Knowledge Graph", "available", "Browse real published topics and their cross-references to Qur'an, Hadith, and Tafsir entities.", "/topics"),
      f("research-engine", "Research Engine", "backend-only", "See Scholarship world."),
      f("translation-i", "Translation", "backend-only", "See Knowledge world."),
      f("arabic-analysis", "Arabic Analysis", "planned", "See Education world."),
      f("local-ai", "Private, self-hosted AI provider", "backend-only", "General AI features run on a private, self-hosted model rather than a third-party API, so no conversation data leaves the platform."),
    ],
  },
  {
    slug: "education",
    name: "Education",
    nameAr: "التعليم",
    tagline: "A real learning path, not a feed.",
    taglineAr: "مسار تعليمي حقيقي، لا موجز أخبار.",
    features: [
      f("islamic-education", "Islamic Education", "available", "Curriculum-governed learning modules with progress tracking.", "/learning"),
      f("courses", "Courses", "available", "See Islamic Education.", "/learning"),
      f("learning-paths", "Learning paths", "backend-only", "Not built yet."),
      f("children-ed", "Children", "planned", "Not built yet."),
      f("new-muslims", "New Muslims", "planned", "Not built yet."),
      f("convert-support", "Convert support", "planned", "Not built yet."),
      f("quran-learning", "Qur'an learning", "planned", "See Hifz/Tajweed."),
      f("hifz-e", "Hifz", "planned", "Not built yet."),
      f("tajweed-e", "Tajweed", "available", "See Ibadah world - tajweed colours in the Qur'an reader.", "/quran/1"),
      f("arabic-e", "Arabic", "planned", "Not built yet."),
      f("hadith-e", "Hadith", "available", "See Knowledge world.", "/hadith"),
      f("fiqh-e", "Fiqh", "planned", "See Knowledge world."),
      f("seerah-e", "Seerah", "planned", "See Knowledge world."),
      f("aqeedah-e", "Aqeedah", "planned", "See Knowledge world."),
      f("quizzes", "Quizzes", "backend-only", "Not built yet."),
      f("progress-tracking", "Progress tracking", "available", "The learning dashboard shows real per-module progress for your account.", "/learning"),
      f("certificates", "Certificates", "planned", "Not built yet."),
      f("personal-learning-plans", "Personal learning plans", "backend-only", "Not built yet."),
    ],
  },
  {
    slug: "world",
    name: "The World",
    nameAr: "العالم",
    tagline: "Every place, person, and institution - connected to the knowledge graph.",
    taglineAr: "كل مكان وشخص ومؤسسة - متصلة بخريطة المعرفة.",
    features: [
      f("countries", "Countries", "planned", "No geodata has been imported."),
      f("cities", "Cities", "planned", "Not built yet."),
      f("mosques", "Mosques", "planned", "See Ummah world."),
      f("scholars-w", "Scholars", "backend-only", "See Scholarship world."),
      f("institutions-w", "Institutions", "backend-only", "See Civilization world."),
      f("universities", "Universities", "planned", "Not built yet."),
      f("organizations-w", "Islamic organizations", "available", "See Ummah world.", "/organisations"),
      f("historical-sites-w", "Historical sites", "planned", "Not built yet."),
      f("civilization-w", "Civilization", "backend-only", "See Civilization world."),
      f("events-w", "Events", "backend-only", "See Ummah world."),
      f("communities-w", "Communities", "backend-only", "See Ummah world."),
      f("businesses-w", "Businesses", "planned", "See Life world."),
      f("humanitarian-w", "Humanitarian activity", "planned", "See Charity world."),
    ],
  },
];

export function findWorld(slug: string): World | undefined {
  return worlds.find((w) => w.slug === slug);
}

export function allFeatures(): Feature[] {
  return worlds.flatMap((w) => w.features);
}

export function featureCounts() {
  const all = allFeatures();
  return {
    total: all.length,
    available: all.filter((x) => x.status === "available").length,
    backendOnly: all.filter((x) => x.status === "backend-only").length,
    planned: all.filter((x) => x.status === "planned").length,
  };
}
