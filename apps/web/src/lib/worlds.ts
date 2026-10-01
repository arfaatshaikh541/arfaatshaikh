// The 85-capability -> 12-world information architecture, with an honest status for every capability.
//
// `status` is load-bearing, not decorative. The vocabulary is fixed (see docs/FEATURE_STATUS.md):
//   IMPLEMENTED            built, tested, and backed by real data or on-device logic that was checked.
//   PARTIALLY_IMPLEMENTED  works, but with a stated gap (limited data, approximation, or a missing layer).
//   DATA_SOURCE_REQUIRED   the feature is built; it needs a licensed/verified dataset (or the owner's rights
//                          confirmation) before it can show content. Its page shows an honest empty state.
//   ARCHITECTURE_READY     the backend, data contract and UI framework exist; nothing is loaded yet.
//   NOT_IMPLEMENTED        nothing built.
//   NOT_VERIFIED           built, but its correctness has not been verified against an authority.
//
// Never mark a capability IMPLEMENTED without a real route that works and evidence that it was tested.

export type FeatureStatus =
  | "IMPLEMENTED"
  | "PARTIALLY_IMPLEMENTED"
  | "DATA_SOURCE_REQUIRED"
  | "ARCHITECTURE_READY"
  | "NOT_IMPLEMENTED"
  | "NOT_VERIFIED";

export const STATUS_ORDER: FeatureStatus[] = ["IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "NOT_VERIFIED", "DATA_SOURCE_REQUIRED", "ARCHITECTURE_READY", "NOT_IMPLEMENTED"];

export interface Feature {
  id: string;
  name: string;
  status: FeatureStatus;
  href?: string;
  note: string;
  /** True only for a real capability that has no dedicated page to link to (background infrastructure). */
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
      f("quran", "Qur'an", "IMPLEMENTED", "Canonical Arabic text (CC BY 4.0), the public-domain Pickthall and Yusuf Ali (1934) translations, reading progress and bookmarks. Further translations stay hidden until their rights are confirmed.", "/quran"),
      f("quran-recitation", "Qur'an Recitation", "DATA_SOURCE_REQUIRED", "The ayah-level player is built. No licensed recitation audio has been supplied.", "/quran"),
      f("salah", "Salah", "NOT_VERIFIED", "Prayer times are computed on your device from astronomical formulas. They have not been checked against an authority's published timetable: follow your local mosque or authority.", "/w/ibadah/tools"),
      f("salah-times", "Salah times", "NOT_VERIFIED", "Same calculator as Salah. Not yet verified against published timetables.", "/w/ibadah/tools"),
      f("qiblah", "Qiblah", "IMPLEMENTED", "Great-circle bearing to the Kaaba from your device location; checked against published bearings for New York and London.", "/w/ibadah/tools"),
      f("dua", "Dua", "DATA_SOURCE_REQUIRED", "The reader is built. The Hisn al-Muslim data's upstream compilation is undocumented, so it stays hidden until its terms are confirmed.", "/hadith/hisn/1/1"),
      f("dhikr", "Dhikr", "DATA_SOURCE_REQUIRED", "The reader is built. The adhkar data's upstream is undocumented, so it stays hidden until its terms are confirmed.", "/hadith/adhkar/1/1"),
      f("dhikr-counter", "Dhikr Counter", "IMPLEMENTED", "A private, on-device tally counter.", "/w/ibadah/tools"),
      f("fasting", "Fasting", "PARTIALLY_IMPLEMENTED", "Fasting log saved on your device; suhoor and iftar times use the unverified prayer-time calculator.", "/w/ibadah/planner"),
      f("ramadan", "Ramadan", "PARTIALLY_IMPLEMENTED", "Ramadan dates from the Umm al-Qura calendar (checked for 1446); local moon-sighting can differ by a day. Suhoor and iftar times use the unverified prayer-time calculator.", "/w/ibadah/planner"),
      f("zakat", "Zakat", "IMPLEMENTED", "Checks a zakat fund's configuration against acceptance rules. Not a fund manager: no funds are held here.", "/w/charity/zakat-checker"),
      f("zakat-calculator", "Zakat calculator", "IMPLEMENTED", "2.5% of net wealth at or above the nisab you enter. Calculated on your device; it does not decide madhhab differences.", "/w/charity/zakat-calculator"),
      f("sadaqah", "Sadaqah", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("hajj", "Hajj", "PARTIALLY_IMPLEMENTED", "Day of Arafah and Eid dates with a countdown (Umm al-Qura). Step-by-step guidance needs a sourced dataset.", "/w/ibadah/planner"),
      f("umrah", "Umrah", "NOT_IMPLEMENTED", "Not built yet."),
      f("islamic-calendar", "Islamic Calendar", "IMPLEMENTED", "Hijri date by the Umm al-Qura calendar (checked against known dates). Local moon sighting may differ by a day.", "/w/ibadah/tools"),
      f("moon", "Moon", "IMPLEMENTED", "Moon phase, age and the next new and full moon; checked against known astronomical events (approximate).", "/w/ibadah/planner"),
      f("janazah", "Janazah", "NOT_IMPLEMENTED", "Not built yet."),
      f("islamic-will", "Islamic Will", "NOT_IMPLEMENTED", "Not built yet."),
      f("hifz", "Hifz", "IMPLEMENTED", "Mark memorised surahs and see progress, saved on your device.", "/w/ibadah/planner"),
      f("tajweed", "Tajweed", "IMPLEMENTED", "Tajweed colour-coding from a CC BY 4.0 rule corpus; every span checked to lie inside its ayah.", "/quran/1"),
      f("worship-tracking", "Worship tracking", "IMPLEMENTED", "Daily prayer checklist and streak, saved on your device.", "/w/ibadah/planner"),
      f("offline-quran", "Offline Qur'an", "IMPLEMENTED", "Download the Qur'an's Arabic text to this device and read it without a connection.", "/offline"),
      { ...f("offline-app-shell", "Offline app shell", "PARTIALLY_IMPLEMENTED", "Pages you have visited reopen offline. Only the Qur'an text is available offline; everything else needs a connection."), pageless: true },
    ],
  },
  {
    slug: "knowledge",
    name: "Knowledge",
    nameAr: "المعرفة",
    tagline: "Text before commentary. Commentary before opinion.",
    taglineAr: "النص قبل الشرح، والشرح قبل الرأي.",
    features: [
      f("quran-k", "Qur'an", "IMPLEMENTED", "See Ibadah - the reader lives in one place.", "/quran"),
      f("tafsir", "Tafsir", "DATA_SOURCE_REQUIRED", "The reader is built and verified for 45 Arabic and 9 English editions. They are hidden until the digital editions' rights are confirmed.", "/tafsir/1/1"),
      f("hadith", "Hadith", "PARTIALLY_IMPLEMENTED", "Sahih al-Bukhari and Sahih Muslim in Arabic, with search and bookmarks. English translations stay hidden until their rights are confirmed; imported hadith gradings stay hidden until their rights are confirmed.", "/hadith"),
      f("fiqh", "Fiqh", "ARCHITECTURE_READY", "Contract, importer, admin workflow and empty-state page exist; no licensed fiqh dataset is loaded.", "/knowledge/fiqh"),
      f("aqeedah", "Aqeedah", "ARCHITECTURE_READY", "As Fiqh: ready for a licensed dataset.", "/knowledge/aqeedah"),
      f("seerah", "Seerah", "ARCHITECTURE_READY", "As Fiqh: ready for a licensed dataset.", "/knowledge/seerah"),
      f("arabic", "Arabic", "NOT_IMPLEMENTED", "See Education world for the Arabic-learning slot."),
      f("translation", "Translation", "PARTIALLY_IMPLEMENTED", "Pickthall and Yusuf Ali (1934) are public; 482 other editions in 97 languages are stored and hidden until rights are confirmed.", "/quran/1"),
      f("terminology", "Islamic terminology", "ARCHITECTURE_READY", "As Fiqh: ready for a licensed glossary.", "/knowledge/terminology"),
      f("cross-references", "Cross references", "DATA_SOURCE_REQUIRED", "The cross-reference and topic system is built; no editorial topics or cross-references have been supplied.", "/topics"),
      f("commentary", "Scholarly commentary", "DATA_SOURCE_REQUIRED", "See Tafsir.", "/tafsir/1/1"),
      f("library", "Islamic Library", "ARCHITECTURE_READY", "Catalogue contract and importer are ready; no licensed catalogue has been supplied.", "/knowledge/library_work"),
    ],
  },
  {
    slug: "scholarship",
    name: "Scholarship",
    nameAr: "العلم الشرعي",
    tagline: "Qur'an. Hadith. Classical scholarship. Contemporary scholarship. AI synthesis. Never blurred together.",
    taglineAr: "القرآن، الحديث، العلم الكلاسيكي، العلم المعاصر، وتوليف الذكاء الاصطناعي - كل منها منفصل وواضح.",
    features: [
      f("scholars", "Scholars", "ARCHITECTURE_READY", "Scholar record contract and importer are ready; a scholar is published only with a sourced biography.", "/knowledge/scholar"),
      f("scholarly-works", "Scholarly works", "ARCHITECTURE_READY", "Ready for a sourced works catalogue.", "/knowledge/book"),
      f("fatwa-references", "Fatwa references", "DATA_SOURCE_REQUIRED", "Requires a licensed, attributed fatwa corpus. The assistant never issues fatwas."),
      f("research", "Research", "NOT_IMPLEMENTED", "Research workspace backend exists; there is no user interface yet."),
      f("source-explorer", "Source explorer", "IMPLEMENTED", "Every source's registry status, licence, and review state - what backs the whole platform's evidence claims.", "/source-registry"),
      f("evidence", "Evidence", "IMPLEMENTED", "Every assistant answer separates primary sources, scholarly explanation and secondary sources, with exact quoted text.", "/assistant"),
      f("citations", "Citations", "IMPLEMENTED", "Every sentence of an answer carries a citation to a stored passage; AI summaries that cite a non-existent source are rejected.", "/assistant"),
      f("hadith-grading", "Hadith grading", "DATA_SOURCE_REQUIRED", "21,185 per-grader gradings are imported but hidden until the right to publish them is confirmed. A grade is accepted only with a named grader and a citable source.", "/knowledge/hadith_grading"),
      f("narrator-info", "Narrator information", "DATA_SOURCE_REQUIRED", "The isnad viewer is built; no narrator/isnad dataset is loaded.", "/hadith"),
      f("schools-of-fiqh", "Schools of fiqh", "DATA_SOURCE_REQUIRED", "Requires sourced fiqh data.", "/knowledge/fiqh"),
      f("scholarly-differences", "Scholarly differences", "PARTIALLY_IMPLEMENTED", "When several scholars comment on a reference, the assistant lists each attributed view separately; it never merges or ranks them. Broader fiqh differences need data.", "/assistant"),
      f("primary-sources", "Primary-source references", "IMPLEMENTED", "See Source explorer.", "/source-registry"),
      f("source-verification", "Source verification", "IMPLEMENTED", "See Source explorer.", "/source-registry"),
      f("research-notes", "Research notes", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
    ],
  },
  {
    slug: "civilization",
    name: "Civilization",
    nameAr: "الحضارة",
    tagline: "The intellectual history, not the mythology.",
    taglineAr: "التاريخ الفكري، لا الأساطير.",
    features: [
      f("history", "Islamic History", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/history"),
      f("civilization-timeline", "Islamic Civilization", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/civilization"),
      f("timelines", "Historical timelines", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/history"),
      f("maps", "Historical maps", "NOT_IMPLEMENTED", "See The World for the live-map slot."),
      f("dynasties", "Dynasties", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/history"),
      f("scholars-c", "Scholars", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/scholar"),
      f("scientists", "Scientists", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/person"),
      f("cities", "Cities", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/place"),
      f("institutions", "Institutions", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/institution"),
      f("manuscripts", "Manuscripts", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/library_work"),
      f("architecture", "Architecture", "NOT_IMPLEMENTED", "Not built yet."),
      f("art", "Art", "NOT_IMPLEMENTED", "Not built yet."),
      f("calligraphy", "Calligraphy", "NOT_IMPLEMENTED", "Not built yet."),
      f("science", "Science", "NOT_IMPLEMENTED", "Not built yet."),
      f("medicine", "Medicine", "NOT_IMPLEMENTED", "Not built yet."),
      f("astronomy", "Astronomy", "IMPLEMENTED", "See Ibadah tools - the Qibla/prayer-time calculators use real solar-position astronomy.", "/w/ibadah/tools"),
      f("mathematics", "Mathematics", "NOT_IMPLEMENTED", "Not built yet."),
      f("philosophy", "Philosophy", "NOT_IMPLEMENTED", "Not built yet."),
      f("libraries", "Libraries", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/library_work"),
    ],
  },
  {
    slug: "family",
    name: "Family",
    nameAr: "الأسرة",
    tagline: "Sensitive subjects, sourced responsibly.",
    taglineAr: "مواضيع حساسة، بمصادر موثوقة.",
    features: [
      f("muslim-women", "Muslim Women", "NOT_IMPLEMENTED", "Not built yet — requires careful, reviewed sourcing before publishing."),
      f("muslim-men", "Muslim Men", "NOT_IMPLEMENTED", "Not built yet."),
      f("marriage", "Marriage", "NOT_IMPLEMENTED", "Not built yet."),
      f("nikah", "Nikah", "NOT_IMPLEMENTED", "Not built yet."),
      f("family", "Family", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("parenting", "Parenting", "NOT_IMPLEMENTED", "Not built yet."),
      f("children", "Children", "NOT_IMPLEMENTED", "Not built yet."),
      f("inheritance", "Inheritance", "NOT_IMPLEMENTED", "Not built yet — requires reviewed fiqh sourcing before publishing."),
      f("family-education", "Family education", "NOT_IMPLEMENTED", "Not built yet."),
      f("family-rights", "Family rights", "NOT_IMPLEMENTED", "Not built yet."),
      f("relationship-guidance", "Relationship guidance", "NOT_IMPLEMENTED", "Not built yet."),
      f("childrens-education", "Children's Islamic education", "NOT_IMPLEMENTED", "See Education world."),
    ],
  },
  {
    slug: "life",
    name: "Life",
    nameAr: "الحياة",
    tagline: "Where scholarship meets the marketplace - carefully.",
    taglineAr: "حيث يلتقي العلم بالسوق - بعناية.",
    features: [
      f("islamic-finance", "Islamic Finance", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("halal-investment", "Halal Investment Screening", "NOT_IMPLEMENTED", "Not built yet — requires a licensed screening methodology before publishing."),
      f("halal-world", "Halal World", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("ingredient-checker", "Ingredient Checker", "NOT_IMPLEMENTED", "Not built yet — will never claim halal/haram status from image recognition alone."),
      f("halal-certification", "Halal Certification", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("health-services", "Health services", "ARCHITECTURE_READY", "Directory engine is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=health"),
      f("business-directory", "Muslim Business Directory", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=business"),
      f("professional-network", "Muslim Professional Network", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=professional"),
      f("jobs", "Muslim Jobs", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=job"),
      f("travel", "Muslim Travel", "NOT_IMPLEMENTED", "See Journey world."),
      f("marketplace", "Islamic Marketplace", "NOT_IMPLEMENTED", "Not built yet."),
      f("work", "Work", "NOT_IMPLEMENTED", "Not built yet."),
      f("entrepreneurship", "Entrepreneurship", "NOT_IMPLEMENTED", "Not built yet."),
    ],
  },
  {
    slug: "ummah",
    name: "Ummah",
    nameAr: "الأمة",
    tagline: "Community, with moderation and privacy designed in from the start.",
    taglineAr: "مجتمع مبني على الإشراف والخصوصية منذ التصميم.",
    features: [
      f("mosque-directory", "Mosque Directory", "PARTIALLY_IMPLEMENTED", "19,776 mosques in Algeria from OpenStreetMap and Wikidata (open licences), each shown as not verified. Other regions have no data yet: run the OpenStreetMap importer or supply an authorised dataset.", "/directory?type=mosque"),
      f("social-community", "Social Community", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("ummah-net", "Ummah", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("organizations", "Muslim organizations", "IMPLEMENTED", "Organisation workspaces (tenant-scoped) are live today.", "/organisations"),
      f("communities", "Communities", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("events", "Events", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=event"),
      f("volunteering", "Volunteering", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=volunteering"),
      f("businesses", "Muslim businesses", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=business"),
      f("professionals", "Muslim professionals", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=professional"),
      f("emergency-network", "Emergency network", "NOT_IMPLEMENTED", "Not built yet."),
      f("institutions-u", "Institutions", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/institution"),
      f("global-network", "Global Muslim network", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
    ],
  },
  {
    slug: "charity",
    name: "Charity",
    nameAr: "الصدقة",
    tagline: "Every campaign and every figure here is real.",
    taglineAr: "كل حملة وكل رقم هنا حقيقي.",
    features: [
      f("zakat-c", "Zakat", "IMPLEMENTED", "See Ibadah world - the same checker.", "/w/charity/zakat-checker"),
      f("zakat-calculator-c", "Zakat calculator", "IMPLEMENTED", "See Ibadah world - the same calculator.", "/w/charity/zakat-calculator"),
      f("sadaqah-c", "Sadaqah", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("waqf", "Waqf", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("humanitarian-aid", "Humanitarian aid", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=charity"),
      f("verified-orgs", "Verified organizations", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=charity"),
      f("campaigns", "Campaigns", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=charity"),
      f("donation-opportunities", "Donation opportunities", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=charity"),
      f("charity-discovery", "Charity discovery", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=charity"),
      f("charitable-projects", "Charitable projects", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=charity"),
    ],
  },
  {
    slug: "journey",
    name: "Journey",
    nameAr: "الرحلة",
    tagline: "Pilgrimage, time, and place.",
    taglineAr: "الحج والزمان والمكان.",
    features: [
      f("hajj-j", "Hajj", "PARTIALLY_IMPLEMENTED", "See Ibadah world - Hajj and Eid dates.", "/w/ibadah/planner"),
      f("umrah-j", "Umrah", "NOT_IMPLEMENTED", "See Ibadah world."),
      f("qiblah-j", "Qiblah", "IMPLEMENTED", "See Ibadah tools.", "/w/ibadah/tools"),
      f("islamic-calendar-j", "Islamic Calendar", "IMPLEMENTED", "See Ibadah tools.", "/w/ibadah/tools"),
      f("moon-j", "Moon", "IMPLEMENTED", "See Ibadah world - moon phase and dates.", "/w/ibadah/planner"),
      f("astronomy-j", "Islamic Astronomy", "IMPLEMENTED", "See Ibadah tools.", "/w/ibadah/tools"),
      f("travel-j", "Muslim Travel", "NOT_IMPLEMENTED", "Not built yet."),
      f("mosque-discovery", "Mosque discovery", "PARTIALLY_IMPLEMENTED", "19,776 mosques in Algeria from OpenStreetMap and Wikidata (open licences), each shown as not verified. Other regions have no data yet: run the OpenStreetMap importer or supply an authorised dataset.", "/directory?type=mosque"),
      f("hajj-prep", "Pilgrimage preparation", "NOT_IMPLEMENTED", "Not built yet."),
      f("hajj-education", "Hajj education", "NOT_IMPLEMENTED", "Not built yet."),
      f("umrah-education", "Umrah education", "NOT_IMPLEMENTED", "Not built yet."),
      f("historical-sites", "Islamic historical sites", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/place"),
    ],
  },
  {
    slug: "intelligence",
    name: "Intelligence",
    nameAr: "الذكاء",
    tagline: "Retrieval, not invention. It never claims to be a scholar.",
    taglineAr: "استرجاع، لا اختلاق - ولا يدّعي أبداً أنه عالم شرعي.",
    features: [
      f("ai-assistant", "Islamic AI Scholar / Assistant", "PARTIALLY_IMPLEMENTED", "Retrieval-grounded answers with ranking, confidence, abstention and validated citations. It answers only from published sources and says 'Insufficient verified sources.' otherwise; an optional local-model summary is shown only if every sentence passes citation validation.", "/assistant"),
      f("islamic-search", "Islamic Search", "IMPLEMENTED", "One search across published Qur'an, hadith, tafsir, topics, courses, knowledge records and directories; every result names its source type.", "/search"),
      f("quran-search", "Qur'an Search", "IMPLEMENTED", "Filter Islamic Search to the Qur'an corpus.", "/search"),
      f("hadith-search", "Hadith Search", "IMPLEMENTED", "Filter Islamic Search to the Hadith corpus.", "/search"),
      f("tafsir-search", "Tafsir Search", "DATA_SOURCE_REQUIRED", "Search works; the tafsir editions are hidden until their rights are confirmed.", "/search"),
      f("fiqh-research", "Fiqh Research", "DATA_SOURCE_REQUIRED", "Depends on the fiqh dataset."),
      f("fact-checker", "Fact Checker", "IMPLEMENTED", "Exact-text check of Arabic passages against the published Qur'an and Hadith.", "/verify"),
      f("quran-verification", "Qur'an Verification", "IMPLEMENTED", "Check whether Arabic text appears word for word in the published Qur'an.", "/verify"),
      f("hadith-verification", "Hadith Verification", "IMPLEMENTED", "Check whether Arabic text appears word for word in the published Hadith collections. It does not grade authenticity.", "/verify"),
      f("source-explorer-i", "Source Explorer", "IMPLEMENTED", "See Scholarship world.", "/source-registry"),
      f("personal-assistant", "Personal Assistant", "NOT_IMPLEMENTED", "Not built yet."),
      f("knowledge-graph", "Knowledge Graph", "PARTIALLY_IMPLEMENTED", "Sourced relationships between ayat, surahs, tafsir works, scholars and tafsir entries, each with its evidence passage. Thematic relationships need editorial data.", "/knowledge/graph"),
      f("research-engine", "Research Engine", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("translation-i", "Translation", "PARTIALLY_IMPLEMENTED", "See Knowledge world.", "/quran/1"),
      f("arabic-analysis", "Arabic Analysis", "NOT_IMPLEMENTED", "See Education world."),
      f("local-ai", "Private, self-hosted AI provider", "NOT_VERIFIED", "Ollama is the default local provider; external providers are off and unsupported. The provider layer is contract-tested, but no model has been run in this environment, so answer-quality and latency are unverified."),
    ],
  },
  {
    slug: "education",
    name: "Education",
    nameAr: "التعليم",
    tagline: "A real learning path, not a feed.",
    taglineAr: "مسار تعليمي حقيقي، لا موجز أخبار.",
    features: [
      f("islamic-education", "Islamic Education", "ARCHITECTURE_READY", "The learning engine (paths, courses, lessons with evidence, quizzes) is built; no course has been published.", "/learning"),
      f("courses", "Courses", "DATA_SOURCE_REQUIRED", "Needs reviewed course content.", "/learning"),
      f("learning-paths", "Learning paths", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("children-ed", "Children", "NOT_IMPLEMENTED", "Not built yet."),
      f("new-muslims", "New Muslims", "NOT_IMPLEMENTED", "Not built yet."),
      f("convert-support", "Convert support", "NOT_IMPLEMENTED", "Not built yet."),
      f("quran-learning", "Qur'an learning", "NOT_IMPLEMENTED", "See Hifz/Tajweed."),
      f("hifz-e", "Hifz", "NOT_IMPLEMENTED", "Not built yet."),
      f("tajweed-e", "Tajweed", "IMPLEMENTED", "See Ibadah world - tajweed colours in the Qur'an reader.", "/quran/1"),
      f("arabic-e", "Arabic", "NOT_IMPLEMENTED", "Not built yet."),
      f("hadith-e", "Hadith", "PARTIALLY_IMPLEMENTED", "See Knowledge world.", "/hadith"),
      f("fiqh-e", "Fiqh", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/fiqh"),
      f("seerah-e", "Seerah", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/seerah"),
      f("aqeedah-e", "Aqeedah", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/aqeedah"),
      f("quizzes", "Quizzes", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("progress-tracking", "Progress tracking", "ARCHITECTURE_READY", "Shows your progress once courses exist.", "/learning"),
      f("certificates", "Certificates", "NOT_IMPLEMENTED", "Not built yet."),
      f("personal-learning-plans", "Personal learning plans", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
    ],
  },
  {
    slug: "world",
    name: "The World",
    nameAr: "العالم",
    tagline: "Every place, person, and institution - connected to the knowledge graph.",
    taglineAr: "كل مكان وشخص ومؤسسة - متصلة بخريطة المعرفة.",
    features: [
      f("countries", "Countries", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/place"),
      f("cities", "Cities", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/place"),
      f("mosques", "Mosques", "PARTIALLY_IMPLEMENTED", "19,776 mosques in Algeria from OpenStreetMap and Wikidata (open licences), each shown as not verified. Other regions have no data yet: run the OpenStreetMap importer or supply an authorised dataset.", "/directory?type=mosque"),
      f("scholars-w", "Scholars", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/scholar"),
      f("institutions-w", "Institutions", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/institution"),
      f("universities", "Universities", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/institution"),
      f("organizations-w", "Islamic organizations", "IMPLEMENTED", "See Ummah world.", "/organisations"),
      f("historical-sites-w", "Historical sites", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/place"),
      f("civilization-w", "Civilization", "ARCHITECTURE_READY", "Data contract, importer and admin workflow are ready; no licensed dataset is loaded.", "/knowledge/civilization"),
      f("events-w", "Events", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=event"),
      f("communities-w", "Communities", "NOT_IMPLEMENTED", "Backend policy logic exists; there is no user interface yet."),
      f("businesses-w", "Businesses", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=business"),
      f("humanitarian-w", "Humanitarian activity", "ARCHITECTURE_READY", "Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset.", "/directory?type=charity"),
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
  const byStatus = Object.fromEntries(STATUS_ORDER.map((status) => [status, all.filter((x) => x.status === status).length])) as Record<FeatureStatus, number>;
  return { total: all.length, byStatus, live: byStatus.IMPLEMENTED + byStatus.PARTIALLY_IMPLEMENTED };
}
