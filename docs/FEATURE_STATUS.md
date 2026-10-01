# Feature status

Generated from `apps/web/src/lib/worlds.ts` by `apps/web/scripts/export-feature-status.mjs`. Do not edit by hand.

175 capabilities across 12 worlds.

| Status | Count | Meaning |
|---|---|---|
| IMPLEMENTED | 34 | Built, tested, and backed by real data or on-device logic that was checked. |
| PARTIALLY_IMPLEMENTED | 12 | Works, with a stated gap (limited data, an approximation, or a missing layer). |
| NOT_VERIFIED | 3 | Built, but its correctness has not been verified against an authority. |
| DATA_SOURCE_REQUIRED | 13 | Built; needs a licensed/verified dataset or the owner's rights confirmation before it can show content. |
| ARCHITECTURE_READY | 51 | Backend, data contract and UI framework exist; nothing is loaded yet. |
| NOT_IMPLEMENTED | 62 | Nothing built. |

## Ibadah (العبادة)

| Capability | Status | Note |
|---|---|---|
| Qur'an | IMPLEMENTED | Canonical Arabic text (CC BY 4.0), the public-domain Pickthall and Yusuf Ali (1934) translations, reading progress and bookmarks. Further translations stay hidden until their rights are confirmed. |
| Qur'an Recitation | DATA_SOURCE_REQUIRED | The ayah-level player is built. No licensed recitation audio has been supplied. |
| Salah | NOT_VERIFIED | Prayer times are computed on your device from astronomical formulas. They have not been checked against an authority's published timetable: follow your local mosque or authority. |
| Salah times | NOT_VERIFIED | Same calculator as Salah. Not yet verified against published timetables. |
| Qiblah | IMPLEMENTED | Great-circle bearing to the Kaaba from your device location; checked against published bearings for New York and London. |
| Dua | DATA_SOURCE_REQUIRED | The reader is built. The Hisn al-Muslim data's upstream compilation is undocumented, so it stays hidden until its terms are confirmed. |
| Dhikr | DATA_SOURCE_REQUIRED | The reader is built. The adhkar data's upstream is undocumented, so it stays hidden until its terms are confirmed. |
| Dhikr Counter | IMPLEMENTED | A private, on-device tally counter. |
| Fasting | PARTIALLY_IMPLEMENTED | Fasting log saved on your device; suhoor and iftar times use the unverified prayer-time calculator. |
| Ramadan | PARTIALLY_IMPLEMENTED | Ramadan dates from the Umm al-Qura calendar (checked for 1446); local moon-sighting can differ by a day. Suhoor and iftar times use the unverified prayer-time calculator. |
| Zakat | IMPLEMENTED | Checks a zakat fund's configuration against acceptance rules. Not a fund manager: no funds are held here. |
| Zakat calculator | IMPLEMENTED | 2.5% of net wealth at or above the nisab you enter. Calculated on your device; it does not decide madhhab differences. |
| Sadaqah | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Hajj | PARTIALLY_IMPLEMENTED | Day of Arafah and Eid dates with a countdown (Umm al-Qura). Step-by-step guidance needs a sourced dataset. |
| Umrah | NOT_IMPLEMENTED | Not built yet. |
| Islamic Calendar | IMPLEMENTED | Hijri date by the Umm al-Qura calendar (checked against known dates). Local moon sighting may differ by a day. |
| Moon | IMPLEMENTED | Moon phase, age and the next new and full moon; checked against known astronomical events (approximate). |
| Janazah | NOT_IMPLEMENTED | Not built yet. |
| Islamic Will | NOT_IMPLEMENTED | Not built yet. |
| Hifz | IMPLEMENTED | Mark memorised surahs and see progress, saved on your device. |
| Tajweed | IMPLEMENTED | Tajweed colour-coding from a CC BY 4.0 rule corpus; every span checked to lie inside its ayah. |
| Worship tracking | IMPLEMENTED | Daily prayer checklist and streak, saved on your device. |
| Offline Qur'an | IMPLEMENTED | Download the Qur'an's Arabic text to this device and read it without a connection. |
| Offline app shell | PARTIALLY_IMPLEMENTED | Pages you have visited reopen offline. Only the Qur'an text is available offline; everything else needs a connection. |

## Knowledge (المعرفة)

| Capability | Status | Note |
|---|---|---|
| Qur'an | IMPLEMENTED | See Ibadah - the reader lives in one place. |
| Tafsir | DATA_SOURCE_REQUIRED | The reader is built and verified for 45 Arabic and 9 English editions. They are hidden until the digital editions' rights are confirmed. |
| Hadith | PARTIALLY_IMPLEMENTED | Sahih al-Bukhari and Sahih Muslim in Arabic, with search and bookmarks. English translations stay hidden until their rights are confirmed; no hadith grading data is loaded. |
| Fiqh | ARCHITECTURE_READY | Contract, importer, admin workflow and empty-state page exist; no licensed fiqh dataset is loaded. |
| Aqeedah | ARCHITECTURE_READY | As Fiqh: ready for a licensed dataset. |
| Seerah | ARCHITECTURE_READY | As Fiqh: ready for a licensed dataset. |
| Arabic | NOT_IMPLEMENTED | See Education world for the Arabic-learning slot. |
| Translation | PARTIALLY_IMPLEMENTED | Pickthall and Yusuf Ali (1934) are public; 482 other editions in 97 languages are stored and hidden until rights are confirmed. |
| Islamic terminology | ARCHITECTURE_READY | As Fiqh: ready for a licensed glossary. |
| Cross references | DATA_SOURCE_REQUIRED | The cross-reference and topic system is built; no editorial topics or cross-references have been supplied. |
| Scholarly commentary | DATA_SOURCE_REQUIRED | See Tafsir. |
| Islamic Library | ARCHITECTURE_READY | Catalogue contract and importer are ready; no licensed catalogue has been supplied. |

## Scholarship (العلم الشرعي)

| Capability | Status | Note |
|---|---|---|
| Scholars | ARCHITECTURE_READY | Scholar record contract and importer are ready; a scholar is published only with a sourced biography. |
| Scholarly works | ARCHITECTURE_READY | Ready for a sourced works catalogue. |
| Fatwa references | DATA_SOURCE_REQUIRED | Requires a licensed, attributed fatwa corpus. The assistant never issues fatwas. |
| Research | NOT_IMPLEMENTED | Research workspace backend exists; there is no user interface yet. |
| Source explorer | IMPLEMENTED | Every source's registry status, licence, and review state - what backs the whole platform's evidence claims. |
| Evidence | IMPLEMENTED | Every assistant answer separates primary sources, scholarly explanation and secondary sources, with exact quoted text. |
| Citations | IMPLEMENTED | Every sentence of an answer carries a citation to a stored passage; AI summaries that cite a non-existent source are rejected. |
| Hadith grading | DATA_SOURCE_REQUIRED | A grade is accepted only with a named grader and a citable source. No such dataset is loaded. |
| Narrator information | DATA_SOURCE_REQUIRED | The isnad viewer is built; no narrator/isnad dataset is loaded. |
| Schools of fiqh | DATA_SOURCE_REQUIRED | Requires sourced fiqh data. |
| Scholarly differences | PARTIALLY_IMPLEMENTED | When several scholars comment on a reference, the assistant lists each attributed view separately; it never merges or ranks them. Broader fiqh differences need data. |
| Primary-source references | IMPLEMENTED | See Source explorer. |
| Source verification | IMPLEMENTED | See Source explorer. |
| Research notes | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |

## Civilization (الحضارة)

| Capability | Status | Note |
|---|---|---|
| Islamic History | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Islamic Civilization | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Historical timelines | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Historical maps | NOT_IMPLEMENTED | See The World for the live-map slot. |
| Dynasties | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Scholars | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Scientists | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Cities | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Institutions | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Manuscripts | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Architecture | NOT_IMPLEMENTED | Not built yet. |
| Art | NOT_IMPLEMENTED | Not built yet. |
| Calligraphy | NOT_IMPLEMENTED | Not built yet. |
| Science | NOT_IMPLEMENTED | Not built yet. |
| Medicine | NOT_IMPLEMENTED | Not built yet. |
| Astronomy | IMPLEMENTED | See Ibadah tools - the Qibla/prayer-time calculators use real solar-position astronomy. |
| Mathematics | NOT_IMPLEMENTED | Not built yet. |
| Philosophy | NOT_IMPLEMENTED | Not built yet. |
| Libraries | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |

## Family (الأسرة)

| Capability | Status | Note |
|---|---|---|
| Muslim Women | NOT_IMPLEMENTED | Not built yet — requires careful, reviewed sourcing before publishing. |
| Muslim Men | NOT_IMPLEMENTED | Not built yet. |
| Marriage | NOT_IMPLEMENTED | Not built yet. |
| Nikah | NOT_IMPLEMENTED | Not built yet. |
| Family | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Parenting | NOT_IMPLEMENTED | Not built yet. |
| Children | NOT_IMPLEMENTED | Not built yet. |
| Inheritance | NOT_IMPLEMENTED | Not built yet — requires reviewed fiqh sourcing before publishing. |
| Family education | NOT_IMPLEMENTED | Not built yet. |
| Family rights | NOT_IMPLEMENTED | Not built yet. |
| Relationship guidance | NOT_IMPLEMENTED | Not built yet. |
| Children's Islamic education | NOT_IMPLEMENTED | See Education world. |

## Life (الحياة)

| Capability | Status | Note |
|---|---|---|
| Islamic Finance | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Halal Investment Screening | NOT_IMPLEMENTED | Not built yet — requires a licensed screening methodology before publishing. |
| Halal World | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Ingredient Checker | NOT_IMPLEMENTED | Not built yet — will never claim halal/haram status from image recognition alone. |
| Halal Certification | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Health services | ARCHITECTURE_READY | Directory engine is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Muslim Business Directory | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Muslim Professional Network | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Muslim Jobs | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Muslim Travel | NOT_IMPLEMENTED | See Journey world. |
| Islamic Marketplace | NOT_IMPLEMENTED | Not built yet. |
| Work | NOT_IMPLEMENTED | Not built yet. |
| Entrepreneurship | NOT_IMPLEMENTED | Not built yet. |

## Ummah (الأمة)

| Capability | Status | Note |
|---|---|---|
| Mosque Directory | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Social Community | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Ummah | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Muslim organizations | IMPLEMENTED | Organisation workspaces (tenant-scoped) are live today. |
| Communities | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Events | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Volunteering | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Muslim businesses | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Muslim professionals | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Emergency network | NOT_IMPLEMENTED | Not built yet. |
| Institutions | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Global Muslim network | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |

## Charity (الصدقة)

| Capability | Status | Note |
|---|---|---|
| Zakat | IMPLEMENTED | See Ibadah world - the same checker. |
| Zakat calculator | IMPLEMENTED | See Ibadah world - the same calculator. |
| Sadaqah | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Waqf | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Humanitarian aid | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Verified organizations | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Campaigns | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Donation opportunities | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Charity discovery | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Charitable projects | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |

## Journey (الرحلة)

| Capability | Status | Note |
|---|---|---|
| Hajj | PARTIALLY_IMPLEMENTED | See Ibadah world - Hajj and Eid dates. |
| Umrah | NOT_IMPLEMENTED | See Ibadah world. |
| Qiblah | IMPLEMENTED | See Ibadah tools. |
| Islamic Calendar | IMPLEMENTED | See Ibadah tools. |
| Moon | IMPLEMENTED | See Ibadah world - moon phase and dates. |
| Islamic Astronomy | IMPLEMENTED | See Ibadah tools. |
| Muslim Travel | NOT_IMPLEMENTED | Not built yet. |
| Mosque discovery | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Pilgrimage preparation | NOT_IMPLEMENTED | Not built yet. |
| Hajj education | NOT_IMPLEMENTED | Not built yet. |
| Umrah education | NOT_IMPLEMENTED | Not built yet. |
| Islamic historical sites | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |

## Intelligence (الذكاء)

| Capability | Status | Note |
|---|---|---|
| Islamic AI Scholar / Assistant | PARTIALLY_IMPLEMENTED | Retrieval-grounded answers with ranking, confidence, abstention and validated citations. It answers only from published sources and says 'Insufficient verified sources.' otherwise; an optional local-model summary is shown only if every sentence passes citation validation. |
| Islamic Search | IMPLEMENTED | One search across published Qur'an, hadith, tafsir, topics, courses, knowledge records and directories; every result names its source type. |
| Qur'an Search | IMPLEMENTED | Filter Islamic Search to the Qur'an corpus. |
| Hadith Search | IMPLEMENTED | Filter Islamic Search to the Hadith corpus. |
| Tafsir Search | DATA_SOURCE_REQUIRED | Search works; the tafsir editions are hidden until their rights are confirmed. |
| Fiqh Research | DATA_SOURCE_REQUIRED | Depends on the fiqh dataset. |
| Fact Checker | IMPLEMENTED | Exact-text check of Arabic passages against the published Qur'an and Hadith. |
| Qur'an Verification | IMPLEMENTED | Check whether Arabic text appears word for word in the published Qur'an. |
| Hadith Verification | IMPLEMENTED | Check whether Arabic text appears word for word in the published Hadith collections. It does not grade authenticity. |
| Source Explorer | IMPLEMENTED | See Scholarship world. |
| Personal Assistant | NOT_IMPLEMENTED | Not built yet. |
| Knowledge Graph | PARTIALLY_IMPLEMENTED | Sourced relationships between ayat, surahs, tafsir works, scholars and tafsir entries, each with its evidence passage. Thematic relationships need editorial data. |
| Research Engine | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Translation | PARTIALLY_IMPLEMENTED | See Knowledge world. |
| Arabic Analysis | NOT_IMPLEMENTED | See Education world. |
| Private, self-hosted AI provider | NOT_VERIFIED | Ollama is the default local provider; external providers are off and unsupported. The provider layer is contract-tested, but no model has been run in this environment, so answer-quality and latency are unverified. |

## Education (التعليم)

| Capability | Status | Note |
|---|---|---|
| Islamic Education | ARCHITECTURE_READY | The learning engine (paths, courses, lessons with evidence, quizzes) is built; no course has been published. |
| Courses | DATA_SOURCE_REQUIRED | Needs reviewed course content. |
| Learning paths | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Children | NOT_IMPLEMENTED | Not built yet. |
| New Muslims | NOT_IMPLEMENTED | Not built yet. |
| Convert support | NOT_IMPLEMENTED | Not built yet. |
| Qur'an learning | NOT_IMPLEMENTED | See Hifz/Tajweed. |
| Hifz | NOT_IMPLEMENTED | Not built yet. |
| Tajweed | IMPLEMENTED | See Ibadah world - tajweed colours in the Qur'an reader. |
| Arabic | NOT_IMPLEMENTED | Not built yet. |
| Hadith | PARTIALLY_IMPLEMENTED | See Knowledge world. |
| Fiqh | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Seerah | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Aqeedah | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Quizzes | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Progress tracking | ARCHITECTURE_READY | Shows your progress once courses exist. |
| Certificates | NOT_IMPLEMENTED | Not built yet. |
| Personal learning plans | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |

## The World (العالم)

| Capability | Status | Note |
|---|---|---|
| Countries | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Cities | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Mosques | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Scholars | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Institutions | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Universities | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Islamic organizations | IMPLEMENTED | See Ummah world. |
| Historical sites | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Civilization | ARCHITECTURE_READY | Data contract, importer and admin workflow are ready; no licensed dataset is loaded. |
| Events | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Communities | NOT_IMPLEMENTED | Backend policy logic exists; there is no user interface yet. |
| Businesses | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
| Humanitarian activity | ARCHITECTURE_READY | Directory engine (search, filters, location, verification, reporting, moderation) is built; no listings are loaded. Suggest one or supply an authorised dataset. |
