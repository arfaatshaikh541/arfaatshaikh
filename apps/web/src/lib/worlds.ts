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
      f("dua", "Dua", "planned", "No reviewed dua collection has been imported yet."),
      f("dhikr", "Dhikr", "planned", "No reviewed dhikr collection has been imported yet."),
      f("dhikr-counter", "Dhikr Counter", "available", "A private, on-device tally counter - no account or server data required.", "/w/ibadah/tools"),
      f("fasting", "Fasting", "planned", "Architecture slot only - no fasting-tracking feature built yet."),
      f("ramadan", "Ramadan", "planned", "Architecture slot only."),
      f("zakat", "Zakat", "available", "A real governance acceptance checker for zakat fund configuration - not a real fund management system (no real funds are stored yet).", "/w/charity/zakat-checker"),
      f("sadaqah", "Sadaqah", "backend-only", "Covered by the same milestone-16 backend; no frontend yet."),
      f("hajj", "Hajj", "planned", "Architecture slot only."),
      f("umrah", "Umrah", "planned", "Architecture slot only."),
      f("islamic-calendar", "Islamic Calendar", "available", "Hijri date shown via the platform's standard calendar conversion (an approximation - local moon-sighting authorities may differ by a day).", "/w/ibadah/tools"),
      f("moon", "Moon", "planned", "Architecture slot only."),
      f("janazah", "Janazah", "planned", "Architecture slot only."),
      f("islamic-will", "Islamic Will", "planned", "Architecture slot only."),
      f("hifz", "Hifz", "planned", "Memorization tracking is not built yet."),
      f("tajweed", "Tajweed", "planned", "Architecture slot only."),
      f("worship-tracking", "Worship tracking", "planned", "Architecture slot only."),
      f("offline-quran", "Offline Qur'an", "planned", "A real, verified offline app-shell (service worker) exists (see docs/deployment/offline.md), but no Qur'an corpus is cached or bundled - there is none in this environment to cache, and doing so needs a licensing review first."),
      { ...f("offline-app-shell", "Offline app shell", "available", "A real, tested service worker caches visited pages and static assets for offline reload - verified with a real browser context set fully offline, not simulated. No Islamic content is cached (see docs/deployment/offline.md)."), pageless: true },
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
      f("tafsir", "Tafsir", "available", "Reviewed commentary, ayah by ayah, separated from and attributed apart from the Qur'anic text.", "/tafsir/study"),
      f("hadith", "Hadith", "available", "Collection -> book -> chapter -> narration, with isnad and bookmarks.", "/hadith/bukhari/1/1"),
      f("fiqh", "Fiqh", "planned", "Architecture slot only - no fiqh knowledge base imported."),
      f("aqeedah", "Aqeedah", "planned", "Architecture slot only."),
      f("seerah", "Seerah", "planned", "Architecture slot only."),
      f("arabic", "Arabic", "planned", "See Education world for the Arabic-learning slot."),
      f("translation", "Translation", "backend-only", "Translation governance (editions, provenance, review) exists in the API; surfaced today only inside the Qur'an/Tafsir readers."),
      f("terminology", "Islamic terminology", "planned", "Architecture slot only."),
      f("cross-references", "Cross references", "available", "Real, published cross-references between Qur'an ayat, Hadith narrations, Tafsir entries, and topics.", "/topics"),
      f("commentary", "Scholarly commentary", "available", "See Tafsir.", "/tafsir/study"),
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
      f("scholars", "Scholars", "backend-only", "Scholarly-collaboration and lineage models exist in the API (milestones 8, 18); no public directory UI yet - and none will be published without verified biographical sourcing."),
      f("scholarly-works", "Scholarly works", "planned", "Architecture slot only."),
      f("fatwa-references", "Fatwa references", "planned", "Architecture slot only."),
      f("research", "Research", "available", "Research workspace for source-linked notes.", "/w/scholarship"),
      f("source-explorer", "Source explorer", "available", "Every source's registry status, licence, and review state - what backs the whole platform's evidence claims.", "/source-registry"),
      f("evidence", "Evidence", "available", "The assistant's retrieval pipeline exposes exact cited text, never paraphrase.", "/assistant"),
      f("citations", "Citations", "available", "Every assistant answer cites its evidence inline; nothing is asserted without one.", "/assistant"),
      f("hadith-grading", "Hadith grading", "planned", "No grading dataset has been imported."),
      f("narrator-info", "Narrator information", "available", "The Hadith reader shows isnad (chain) data where imported.", "/hadith/bukhari/1/1"),
      f("schools-of-fiqh", "Schools of fiqh", "planned", "Architecture slot only."),
      f("scholarly-differences", "Scholarly differences", "planned", "Architecture slot only - this must never be flattened into one answer when built."),
      f("primary-sources", "Primary-source references", "available", "See Source explorer.", "/source-registry"),
      f("source-verification", "Source verification", "available", "See Source explorer.", "/source-registry"),
      f("research-notes", "Research notes", "backend-only", "Research-workspace API exists; no dedicated notes UI yet."),
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
      f("civilization-timeline", "Islamic Civilization", "backend-only", "Civilizational-infrastructure and living-civilization APIs exist (milestones 14-15); no public timeline UI."),
      f("timelines", "Historical timelines", "planned", "Architecture slot only."),
      f("maps", "Historical maps", "planned", "See The World for the live-map slot."),
      f("dynasties", "Dynasties", "planned", "Architecture slot only."),
      f("scholars-c", "Scholars", "backend-only", "See Scholarship world."),
      f("scientists", "Scientists", "planned", "Architecture slot only."),
      f("cities", "Cities", "planned", "See The World."),
      f("institutions", "Institutions", "backend-only", "Institutional-network API exists (milestone 13); no directory UI yet."),
      f("manuscripts", "Manuscripts", "backend-only", "Preservation-archive API exists (milestone 14); no viewer UI yet."),
      f("architecture", "Architecture", "planned", "Architecture slot only."),
      f("art", "Art", "planned", "Architecture slot only."),
      f("calligraphy", "Calligraphy", "planned", "Architecture slot only."),
      f("science", "Science", "planned", "Architecture slot only."),
      f("medicine", "Medicine", "planned", "Architecture slot only."),
      f("astronomy", "Astronomy", "available", "See Ibadah tools - the Qibla/prayer-time calculators use real solar-position astronomy.", "/w/ibadah/tools"),
      f("mathematics", "Mathematics", "planned", "Architecture slot only."),
      f("philosophy", "Philosophy", "planned", "Architecture slot only."),
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
      f("muslim-women", "Muslim Women", "planned", "Architecture slot only - requires careful, reviewed sourcing before publishing."),
      f("muslim-men", "Muslim Men", "planned", "Architecture slot only."),
      f("marriage", "Marriage", "planned", "Architecture slot only."),
      f("nikah", "Nikah", "planned", "Architecture slot only."),
      f("family", "Family", "backend-only", "Family-safeguarding governance exists in the API (milestone 19); no frontend yet."),
      f("parenting", "Parenting", "planned", "Architecture slot only."),
      f("children", "Children", "planned", "Architecture slot only."),
      f("inheritance", "Inheritance", "planned", "Architecture slot only - requires reviewed fiqh sourcing before publishing."),
      f("family-education", "Family education", "planned", "Architecture slot only."),
      f("family-rights", "Family rights", "planned", "Architecture slot only."),
      f("relationship-guidance", "Relationship guidance", "planned", "Architecture slot only."),
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
      f("islamic-finance", "Islamic Finance", "backend-only", "Islamic-finance-governance API exists (milestone 19); educational-only, not financial advice, when built."),
      f("halal-investment", "Halal Investment Screening", "planned", "Architecture slot only - requires a licensed screening methodology before publishing."),
      f("halal-world", "Halal World", "backend-only", "Halal/ethical-commerce governance API exists (milestone 19); no frontend yet."),
      f("ingredient-checker", "Ingredient Checker", "planned", "Architecture slot only - will never claim halal/haram status from image recognition alone."),
      f("halal-certification", "Halal Certification", "backend-only", "See Halal World backend."),
      f("business-directory", "Muslim Business Directory", "planned", "Architecture slot only."),
      f("professional-network", "Muslim Professional Network", "planned", "Architecture slot only."),
      f("jobs", "Muslim Jobs", "planned", "Architecture slot only."),
      f("travel", "Muslim Travel", "planned", "See Journey world."),
      f("marketplace", "Islamic Marketplace", "planned", "Architecture slot only."),
      f("work", "Work", "planned", "Architecture slot only."),
      f("entrepreneurship", "Entrepreneurship", "planned", "Architecture slot only."),
    ],
  },
  {
    slug: "ummah",
    name: "Ummah",
    nameAr: "الأمة",
    tagline: "Community, with moderation and privacy designed in from the start.",
    taglineAr: "مجتمع مبني على الإشراف والخصوصية منذ التصميم.",
    features: [
      f("mosque-directory", "Mosque Directory", "planned", "Architecture slot only - requires a licensed/verified geodata source."),
      f("social-community", "Social Community", "backend-only", "Community-moderation API exists (milestone 8); no public UI yet."),
      f("ummah-net", "Ummah", "backend-only", "Global-ummah-network API exists (milestone 17); no public UI yet."),
      f("organizations", "Muslim organizations", "available", "Organisation workspaces (tenant-scoped) are live today.", "/organisations"),
      f("communities", "Communities", "backend-only", "See Social Community."),
      f("events", "Events", "backend-only", "Civilization-OS events API exists (milestone 18); no public UI yet."),
      f("volunteering", "Volunteering", "planned", "Architecture slot only."),
      f("businesses", "Muslim businesses", "planned", "See Life world."),
      f("professionals", "Muslim professionals", "planned", "See Life world."),
      f("emergency-network", "Emergency network", "planned", "Architecture slot only - a real safety feature needs real operational backing before launch, not a placeholder."),
      f("institutions-u", "Institutions", "backend-only", "See Civilization world."),
      f("global-network", "Global Muslim network", "backend-only", "See Ummah net."),
    ],
  },
  {
    slug: "charity",
    name: "Charity",
    nameAr: "الصدقة",
    tagline: "Never a fabricated campaign, never a fabricated number.",
    taglineAr: "لا حملة وهمية، ولا رقم وهمي - أبداً.",
    features: [
      f("zakat-c", "Zakat", "available", "See Ibadah world - the same real governance checker.", "/w/charity/zakat-checker"),
      f("sadaqah-c", "Sadaqah", "backend-only", "See Ibadah world."),
      f("waqf", "Waqf", "backend-only", "Zakat/waqf-governance API exists (milestone 16); no frontend yet."),
      f("humanitarian-aid", "Humanitarian aid", "planned", "Architecture slot only."),
      f("verified-orgs", "Verified organizations", "planned", "Architecture slot only - will only ever list organizations with a real, checkable verification record."),
      f("campaigns", "Campaigns", "planned", "Architecture slot only."),
      f("donation-opportunities", "Donation opportunities", "planned", "Architecture slot only."),
      f("charity-discovery", "Charity discovery", "planned", "Architecture slot only."),
      f("charitable-projects", "Charitable projects", "planned", "Architecture slot only."),
    ],
  },
  {
    slug: "journey",
    name: "Journey",
    nameAr: "الرحلة",
    tagline: "Pilgrimage, time, and place.",
    taglineAr: "الحج والزمان والمكان.",
    features: [
      f("hajj-j", "Hajj", "planned", "See Ibadah world."),
      f("umrah-j", "Umrah", "planned", "See Ibadah world."),
      f("qiblah-j", "Qiblah", "available", "See Ibadah tools.", "/w/ibadah/tools"),
      f("islamic-calendar-j", "Islamic Calendar", "available", "See Ibadah tools.", "/w/ibadah/tools"),
      f("moon-j", "Moon", "planned", "Architecture slot only."),
      f("astronomy-j", "Islamic Astronomy", "available", "See Ibadah tools.", "/w/ibadah/tools"),
      f("travel-j", "Muslim Travel", "planned", "Architecture slot only."),
      f("mosque-discovery", "Mosque discovery", "planned", "See Ummah world."),
      f("hajj-prep", "Pilgrimage preparation", "planned", "Architecture slot only."),
      f("hajj-education", "Hajj education", "planned", "Architecture slot only."),
      f("umrah-education", "Umrah education", "planned", "Architecture slot only."),
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
      f("ai-assistant", "Islamic AI Scholar / Assistant", "available", "Evidence-grounded: composes an answer only from approved, cited sources - never a generative fabrication.", "/assistant"),
      f("islamic-search", "Islamic Search", "available", "Real full-text search over approved Qur'an, Hadith, and Tafsir text via the retrieval API - not AI-generated.", "/search"),
      f("quran-search", "Qur'an Search", "available", "Filter Islamic Search to the Qur'an corpus.", "/search"),
      f("hadith-search", "Hadith Search", "available", "Filter Islamic Search to the Hadith corpus.", "/search"),
      f("tafsir-search", "Tafsir Search", "available", "Filter Islamic Search to the Tafsir corpus.", "/search"),
      f("fiqh-research", "Fiqh Research", "planned", "Depends on the Fiqh knowledge base in Knowledge world."),
      f("fact-checker", "Fact Checker", "planned", "Architecture slot only."),
      f("quran-verification", "Qur'an Verification", "planned", "Architecture slot only."),
      f("hadith-verification", "Hadith Verification", "planned", "Architecture slot only."),
      f("source-explorer-i", "Source Explorer", "available", "See Scholarship world.", "/source-registry"),
      f("personal-assistant", "Personal Assistant", "planned", "Architecture slot only."),
      f("knowledge-graph", "Knowledge Graph", "available", "Browse real published topics and their cross-references to Qur'an, Hadith, and Tafsir entities.", "/topics"),
      f("research-engine", "Research Engine", "backend-only", "See Scholarship world."),
      f("translation-i", "Translation", "backend-only", "See Knowledge world."),
      f("arabic-analysis", "Arabic Analysis", "planned", "See Education world."),
      f("local-ai", "Local AI provider (Ollama)", "backend-only", "A provider-agnostic AI layer exists server-side (AIProvider -> OllamaProvider), off by default and never calling a paid API - see docs/ai/provider-architecture.md. No local model is installed in this environment, so it correctly reports unavailable rather than fabricating a response."),
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
      f("learning-paths", "Learning paths", "backend-only", "Curriculum-governance API supports sequencing; not yet exposed as a distinct UI concept."),
      f("children-ed", "Children", "planned", "Architecture slot only."),
      f("new-muslims", "New Muslims", "planned", "Architecture slot only."),
      f("convert-support", "Convert support", "planned", "Architecture slot only."),
      f("quran-learning", "Qur'an learning", "planned", "See Hifz/Tajweed."),
      f("hifz-e", "Hifz", "planned", "Architecture slot only."),
      f("tajweed-e", "Tajweed", "planned", "Architecture slot only."),
      f("arabic-e", "Arabic", "planned", "Architecture slot only."),
      f("hadith-e", "Hadith", "available", "See Knowledge world.", "/hadith/bukhari/1/1"),
      f("fiqh-e", "Fiqh", "planned", "See Knowledge world."),
      f("seerah-e", "Seerah", "planned", "See Knowledge world."),
      f("aqeedah-e", "Aqeedah", "planned", "See Knowledge world."),
      f("quizzes", "Quizzes", "backend-only", "Learning-assessment API exists; no quiz UI yet."),
      f("progress-tracking", "Progress tracking", "available", "The learning dashboard shows real per-module progress for your account.", "/learning"),
      f("certificates", "Certificates", "planned", "Architecture slot only."),
      f("personal-learning-plans", "Personal learning plans", "backend-only", "Curriculum-governance API supports this; no dedicated UI yet."),
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
      f("cities", "Cities", "planned", "Architecture slot only."),
      f("mosques", "Mosques", "planned", "See Ummah world."),
      f("scholars-w", "Scholars", "backend-only", "See Scholarship world."),
      f("institutions-w", "Institutions", "backend-only", "See Civilization world."),
      f("universities", "Universities", "planned", "Architecture slot only."),
      f("organizations-w", "Islamic organizations", "available", "See Ummah world.", "/organisations"),
      f("historical-sites-w", "Historical sites", "planned", "Architecture slot only."),
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
