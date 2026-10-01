# Data readiness

Generated from `data/source-manifest.json` by `scripts/generate_data_readiness.py`. Do not edit by hand; edit the manifest and regenerate.
Manifest as of **2026-10-01**. Public = visible to visitors in a production deployment after `scripts/sync_manifest.py`.

## Domain readiness

Generated from `data/domain-readiness.json` (validated against the manifest by `scripts/validate_data.py` and the test-suite). A domain is **READY** only when all twelve gates are met for its stated scope; an importer existing, records being present, or a dataset being published is not enough. Source reachability and licence findings are in [`SOURCE_VERIFICATION.md`](SOURCE_VERIFICATION.md). Nothing here has had a human scholarly or legal review.

- **EMPTY** - No data and no usable source found.
- **SOURCE_BLOCKED** - A legitimate source exists but cannot be reached or accessed from here.
- **SOURCE_UNVERIFIED** - A candidate source exists but its provenance is unclear.
- **RIGHTS_UNVERIFIED** - Data is imported (hidden) or published on declared terms, but publication rights are not established.
- **IMPORT_READY** - Source verified and rights established; importer ready; nothing imported yet.
- **IMPORTED** - Imported and hidden; validation or review incomplete.
- **VALIDATED** - Imported and validated; not yet published.
- **PUBLISHED** - Published with verified rights, but one or more readiness gates are not satisfied (see the gates).
- **READY** - All twelve gates are satisfied for the stated scope.

### The twelve gates

1. `real_source` - A real source exists.
2. `provenance_documented` - The source provenance is documented.
3. `rights_established` - Publication rights are established for the intended use.
4. `retrievable_or_present` - The source can be retrieved/imported, or is already legitimately present.
5. `schema_maps_without_invention` - The schema maps the source without inventing missing values.
6. `validation_passes` - Validation passes.
7. `duplicates_conflicts_deterministic` - Duplicates and conflicts are handled deterministically.
8. `record_level_provenance` - Provenance is retained at record level.
9. `ui_shows_verification_status` - The public UI shows verification status accurately.
10. `assistant_can_cite` - The assistant can cite the published information.
11. `lifecycle_tests` - Tests cover the import and publication lifecycle.
12. `actually_verified` - The result has been verified, not assumed.

### Dashboard

| Domain | Status | Coverage | Records (published / hidden / total) | Source | Licence | Provenance / quality confidence | Validation | Publication |
|---|---|---|---|---|---|---|---|---|
| **Qur'an** | **READY** | FULL | 6236 / 0 / 6236 | PyPI quran-text (quran.ws, KFGQPC text) 0.1.0; fawazahmed0/quran-api for the two translations; npm @quran.ws/tajwid-* 0.1.0 | CC BY 4.0 (text, tajweed); public domain (Pickthall, d. 1936; Yusuf Ali 1934 edition, d. 1953) | high / high | VERIFIED | published |
| **Hadith** | **RIGHTS_UNVERIFIED** | PARTIAL | 14778 / 332 / 15110 | PyPI sahih-al-bukhari 3.1.7, sahih-muslim 1.1.2; npm @kazishariar/nawawi-40-hadith-data 1.0.3 | Packagers declare AGPL-3.0 (Bukhari, Muslim) and CC BY 4.0 (Nawawi); the classical Arabic works are public domain | medium / medium | NEEDS_REVIEW | published |
| **Hadith gradings** | **RIGHTS_UNVERIFIED** | PARTIAL | 0 / 21185 / 21185 | fawazahmed0/hadith-api info.json, git tag 1 | Unlicense (repository). Rights in the compiled grades are not established. | medium / low | NEEDS_REVIEW | hidden |
| **Tafsir** | **RIGHTS_UNVERIFIED** | PARTIAL | 0 / 182320 / 182320 | spa5k/tafsir_api (data compiled from Quran.com / Tarteel QUL / altafsir.com) | Original classical works are public domain; the digital editions' own rights are not stated and modern works are in copyright | medium / medium | VERIFIED | hidden |
| **Fiqh** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Aqeedah** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Seerah** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Scholar biographies** | **SOURCE_BLOCKED** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Islamic terminology** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Islamic history** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Islamic civilization** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Libraries, books and catalogues** | **SOURCE_BLOCKED** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Mosques** | **PUBLISHED** | PARTIAL | 19776 / 5 / 19781 | GeoAlgeria @geoalgeria/mosquees 2.0.4 (composite of Wikidata and OpenStreetMap) | ODbL 1.0 (OpenStreetMap-derived records) and CC0-1.0 (Wikidata records); package code MIT | high / medium | VERIFIED | published |
| **Organisations** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Events** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Charities** | **SOURCE_BLOCKED** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Volunteering** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Businesses** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Professionals** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Health services** | **EMPTY** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Jobs** | **SOURCE_BLOCKED** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |
| **Recitation audio** | **SOURCE_BLOCKED** | NONE | 0 / 0 / 0 | - | - | none / none | NOT_RUN | none |

### Blockers and failing gates

**Qur'an** (READY): scope - Arabic text (Uthmani, Hafs 'an 'Asim), tajweed rules and spans, and two public-domain English translations (Pickthall 1930, Yusuf Ali 1934 edition).

- No blockers.
- Gates not met: none

- Coverage note: 482 further translations are imported but hidden (rights not cleared); recitation audio is a separate domain.

**Hadith** (RIGHTS_UNVERIFIED): scope - Arabic text of Sahih al-Bukhari (7,277), Sahih Muslim (7,459) and Forty Hadith of al-Nawawi (42) is published; English translations, Hisn al-Muslim and adhkar (332) are imported but hidden.

- Blocker: Owner must confirm the AGPL-3.0 position for redistributing the packaged Arabic text (does not affect the public-domain status of the original work).
- Blocker: Nawawi-40 upstream compilation is undocumented; 41 of 42 entries cross-checked verbatim against Bukhari/Muslim.
- Blocker: English translations: translator and publisher permission not documented.
- Blocker: Hisn al-Muslim and adhkar: upstream not documented.
- Gates not met: `rights_established`, `validation_passes`, `actually_verified`

- Coverage note: Only three collections are loaded. The four Sunan, Muwatta and Musnad Ahmad are not.

**Hadith gradings** (RIGHTS_UNVERIFIED): scope - Per-grader grades for Abu Dawud, Ibn Majah, Malik, al-Nasa'i and al-Tirmidhi (collection and number only; the texts are not loaded). Imported and hidden.

- Blocker: The Unlicense covers only the repository author's own work, not the graders' modern published works that the grades were compiled from.
- Blocker: Source sites' terms unreachable; the compilation method (scraping) is evidenced by file names.
- Blocker: Grades not compared with the graders' printed works.
- Blocker: The five graded collections are not loaded, so no record links to hadith text.
- Gates not met: `rights_established`, `schema_maps_without_invention`, `validation_passes`, `ui_shows_verification_status`, `assistant_can_cite`, `actually_verified`

**Tafsir** (RIGHTS_UNVERIFIED): scope - 54 editions (Arabic classical and modern, English) imported with 182,320 entries; all hidden.

- Blocker: Rights of the digital editions are not established; modern works need permission from authors/estates/publishers.
- Blocker: Some editions carry modern editorial notes that would need stripping.
- Gates not met: `rights_established`, `ui_shows_verification_status`, `assistant_can_cite`, `actually_verified`

**Fiqh** (EMPTY): scope - Per-madhhab positions with question, ruling, evidence and a page-level citation.

- Blocker: No openly licensed, verifiable fiqh dataset found.
- Blocker: @al-mabsut/muslimah rejected: no cited work or page, no content licence.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Aqeedah** (EMPTY): scope - Statements per school with work and page citations.

- Blocker: No source found.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Seerah** (EMPTY): scope - Chronology with reliability categories (established, well-known but disputed, weak reports).

- Blocker: No source found; OpenITI licence not established.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Scholar biographies** (SOURCE_BLOCKED): scope - Biographies from verified sources with teachers, students and works.

- Blocker: Wikidata (CC0) is the intended open source but is unreachable from the build environment (2026-10-01).
- Blocker: OpenITI licence not established.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Islamic terminology** (EMPTY): scope - Terms with Arabic, transliteration, definition and sources.

- Blocker: No source found.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Islamic history** (EMPTY): scope - Source-backed timeline with historians' disagreements preserved.

- Blocker: No source found.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Islamic civilization** (EMPTY): scope - Source-backed contributions, institutions, manuscripts.

- Blocker: No source found.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Libraries, books and catalogues** (SOURCE_BLOCKED): scope - Metadata-only or external-link records for works; no copyrighted files.

- Blocker: Open Library, Internet Archive, Gutenberg, Wikidata unreachable (2026-10-01).
- Blocker: OpenITI licence not established.
- Blocker: PyPI 'hadith' (Umma1) bundles unattributed Arabic collections: provenance unclear.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Mosques** (PUBLISHED): scope - Algeria only: 19,781 listings (19,776 visible after 5 probable duplicates were linked). Every listing is 'Not verified'.

- Blocker: Algeria only.
- Blocker: Community composite, not an official registry; individual mosques are not verified in person.
- Blocker: Known source-quality anomalies are retained unchanged (e.g. a former synagogue classified as a mosque by Wikidata); see data/source-quality-notes.json.
- Gates not met: `assistant_can_cite`, `actually_verified`

- Coverage note: Algeria only; no data for any other country. Do not read this as global coverage.

**Organisations** (EMPTY): scope - Islamic organisations and institutions with registration and source.

- Blocker: No source reachable or found; Wikidata and OpenStreetMap unreachable.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Events** (EMPTY): scope - Organiser-supplied events with start/end; expired events disappear.

- Blocker: Organiser-supplied only; Hijri calendar libraries carry no cited authority.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Charities** (SOURCE_BLOCKED): scope - Registered charities with registration and source; no donation links.

- Blocker: National charity registers unreachable (2026-10-01).
- Blocker: A register does not say whether a charity is Muslim.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Volunteering** (EMPTY): scope - Opportunities with organisation, application URL and source.

- Blocker: No source.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Businesses** (EMPTY): scope - Businesses with category, location and source; no ratings.

- Blocker: No open dataset identifies Muslim-owned businesses.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Professionals** (EMPTY): scope - Professionals with registration where legitimate.

- Blocker: Self-registration with moderation is the legitimate route; none registered.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Health services** (EMPTY): scope - Health services without medical claims.

- Blocker: No source.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Jobs** (SOURCE_BLOCKED): scope - Employer-supplied jobs with application URL and expiry.

- Blocker: Job APIs unreachable and need keys and terms acceptance (2026-10-01).
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`

**Recitation audio** (SOURCE_BLOCKED): scope - Per-ayah or per-surah recitation, hosted with checksum or as an external link.

- Blocker: Recitation hosts unreachable from the build environment (everyayah.com, mp3quran.net, api.quran.com, cdn.islamic.network; 2026-10-01).
- Blocker: Reciter and publisher redistribution terms not documented in an accessible form.
- Gates not met: `real_source`, `provenance_documented`, `rights_established`, `retrievable_or_present`, `schema_maps_without_invention`, `validation_passes`, `duplicates_conflicts_deterministic`, `record_level_provenance`, `ui_shows_verification_status`, `assistant_can_cite`, `lifecycle_tests`, `actually_verified`


## Per-source readiness (manifest)

### Per-source readiness legend

- **VERIFIED** - Source, licence and content checks done; safe to publish as described.
- **NEEDS_REVIEW** - Usable and published/staged as stated, but a person must confirm a caveat listed below.
- **LICENSE_REQUIRED** - Content exists but may not be shown publicly until the rights holder's permission is recorded.
- **PROVENANCE_UNCLEAR** - The upstream origin could not be established; hidden until it can be.
- **UNAVAILABLE** - A legitimate source exists but could not be reached from the build environment; run the importer elsewhere.
- **OWNER_UPLOAD_REQUIRED** - No dataset is loaded. The importer, schema and empty-state UI are ready; supply an authorised dataset.

## Summary

| Readiness | Datasets | Public |
|---|---|---|
| VERIFIED | 5 | 5 |
| NEEDS_REVIEW | 3 | 3 |
| LICENSE_REQUIRED | 8 | 0 |
| PROVENANCE_UNCLEAR | 4 | 0 |
| UNAVAILABLE | 0 | 0 |
| OWNER_UPLOAD_REQUIRED | 16 | 0 |

## Every source

| Source | Purpose | Licence | Provenance | Verification | Public | Import method | Last checked | Remaining action |
|---|---|---|---|---|---|---|---|---|
| **Mosques**<br>`directory-mosques`<br>GeoAlgeria @geoalgeria/mosquees (composite of Wikidata and OpenStreetMap) 2.0.4 | Mosques directory (Algeria, from an open composite of Wikidata and OpenStreetMap). | Data: ODbL 1.0 (© OpenStreetMap contributors) and CC0-1.0 (Wikidata); package code: MIT (VERIFIED_OPEN) | npm package @geoalgeria/mosquees 2.0.4 (sha512 integrity verified on download), built 2026-06-25 from Wikidata SPARQL (instances of mosque in Algeria with coordinates) and OpenStreetMap Overpass (amenity=place_of_worship, religion=muslim), merged within ~150 m. Community-maintained composite, not an official registry; the commune is derived by nearest-centroid join. Each listing keeps its Wikidata or OSM reference. | VERIFIED - Automated checks only: licence text read; all coordinates inside Algeria's bounding box; no duplicate ids; every row has source, licence and provenance; contract validation 0 failures; scripts/validate_data.py passes. Individual mosques are NOT verified in person; listings show 'Not verified'. **[VERIFIED]** | yes | scripts/run_importer.py geoalgeria-mosquees [--apply] (all-or-nothing, records source version and checksum), or Data & trust > Importers | 2026-10-01 | Covers Algeria only. Other regions: run scripts/import_osm_mosques.py for your area on a machine that can reach the Overpass API, or upload an authorised national dataset. Individual listings become 'Verified' only through admin moderation. |
| **Qur'an, Arabic text (Uthmani, Hafs 'an 'Asim)**<br>`quran-arabic-uthmani-hafs`<br>PyPI package quran-text (quran.ws, KFGQPC text) 0.1.0 | Primary Qur'an text for the reader, search, verification and assistant. | CC BY 4.0 (VERIFIED_OPEN) | Downloaded from PyPI; wheel sha256 compared with PyPI's published digest before import. | VERIFIED - 114 surahs / 6,236 ayahs; well-known ayahs spot-checked. **[VERIFIED]** | yes | importer script | 2026-10-01 | None. |
| **Tajweed rules and per-ayah spans**<br>`quran-tajweed-quranws`<br>npm @quran.ws/tajwid-rules and @quran.ws/tajwid-annotations (rules from Quranpedia) 0.1.0 | Colour-coded tajweed in the Qur'an reader. | CC BY 4.0 (VERIFIED_OPEN) | npm registry; sha512 integrity from the registry compared before import. | VERIFIED - All 147,255 spans in bounds; all 3,839 qalqalah spans land on a qalqalah letter. **[VERIFIED]** | yes | importer script | 2026-10-01 | None. |
| **Qur'an translation: Marmaduke Pickthall (1930)**<br>`quran-translation-pickthall`<br>fawazahmed0/quran-api edition eng-mohammedmarmadu branch 1 (retrieved 2026-09-30) | English translation in the reader and assistant. | Public domain (translator died 1936; first published 1930) (PUBLIC_DOMAIN) | raw.githubusercontent.com; sha256 recorded. | VERIFIED - 6,236 verses; numbering identical to the Arabic; 100% non-empty. **[VERIFIED]** | yes | importer script | 2026-10-01 | None (public-domain status can differ by jurisdiction; confirm for your audience). |
| **Qur'an translation: Abdullah Yusuf Ali (1934 original edition)**<br>`quran-translation-yusufali-1934`<br>fawazahmed0/quran-api edition eng-yusufaliorig branch 1 (retrieved 2026-09-30) | English translation in the reader and assistant. | Public domain (translator died 1953; 1934 edition) (PUBLIC_DOMAIN) | raw.githubusercontent.com; sha256 recorded. | VERIFIED - 6,236 verses; numbering identical to the Arabic; 100% non-empty. **[VERIFIED]** | yes | importer script | 2026-10-01 | None (jurisdiction note as above). |
| **Sahih al-Bukhari, Arabic text**<br>`hadith-bukhari-arabic`<br>PyPI sahih-al-bukhari 3.1.7 | Primary hadith text for the reader, search and assistant. | Package declares AGPL-3.0; the original classical text is in the public domain (PD_WORK_OPEN_EDITION_DECLARED) | Downloaded from PyPI with checksum verification. | VERIFIED - Hadith 1 matches the expected wording; wheel sha256 matches PyPI. **[NEEDS_REVIEW]** | yes | importer script | 2026-10-01 | Owner to confirm the AGPL-3.0 position for redistributing the Arabic text database (does not affect the original text being public domain). |
| **Sahih Muslim, Arabic text**<br>`hadith-muslim-arabic`<br>PyPI sahih-muslim 1.1.2 | Primary hadith text for the reader, search and assistant. | Package declares AGPL-3.0; the original classical text is in the public domain (PD_WORK_OPEN_EDITION_DECLARED) | Downloaded from PyPI with checksum verification. | VERIFIED - Hadith 1 matches the expected wording; wheel sha256 matches PyPI. **[NEEDS_REVIEW]** | yes | importer script | 2026-10-01 | Owner to confirm the AGPL-3.0 position for redistributing the Arabic text database (does not affect the original text being public domain). |
| **Forty Hadith of al-Nawawi, Arabic text**<br>`hadith-nawawi40-arabic`<br>npm @kazishariar/nawawi-40-hadith-data 1.0.3 | Short curated hadith collection. | Package declares CC BY 4.0; upstream source not documented. Original text is public domain. (PD_WORK_OPEN_EDITION_DECLARED) | npm registry download. | VERIFIED - Arabic cross-checked against Bukhari/Muslim: 41 of 42 entries found verbatim; the remainder are not marked as verified. **[NEEDS_REVIEW]** | yes | importer script | 2026-10-01 | Confirm the upstream compilation's terms. |
| **Qur'an recitation audio**<br>`audio-quran-recitations`<br>No source acquired | Per-ayah audio in the reader. | Reciter and publisher rights not established (LICENSE_REQUIRED) | None. | NOT_RUN - No data. **[LICENSE_REQUIRED]** | no | owner upload | 2026-10-01 | Supply recitation files with the reciter's/publisher's permission and a checksum per file. |
| **Sahih al-Bukhari, English translation**<br>`hadith-bukhari-english`<br>PyPI sahih-al-bukhari 3.1.7 (translation bundled in the package) 3.1.7 | English reading layer for the hadith reader. | Commercially published translation; redistribution rights not established (LICENSE_REQUIRED) | Bundled in the PyPI package; translator/publisher permission not documented. | NEEDS_REVIEW - Aligned 1:1 with the Arabic narrations. **[LICENSE_REQUIRED]** | no | importer script | 2026-10-01 | Obtain permission from the translation's rights holder, then publish with scripts/apply_publication_policy.py after recording rights_confirmation in this entry. |
| **Hadith grading**<br>`hadith-grading`<br>fawazahmed0/hadith-api (info.json, git tag 1) 1 | Hadith grades with the grader and the grading source, one entry per grader; differing grades are kept side by side. | Unlicense (repository). Rights in the grades compiled from the graders' works are not established. (LICENSE_REQUIRED) | info.json of fawazahmed0/hadith-api tag 1, fetched from raw.githubusercontent.com 2026-10-01. Grades for Abu Dawud, Ibn Majah, Malik, al-Nasa'i and al-Tirmidhi, each attributed to a named grader (Al-Albani, Zubair Ali Zai, Shuaib Al Arnaut, Ahmad Muhammad Shakir, Bashar Awad Maarouf, Abu Ghuddah, Muhammad Fouad Abd al-Baqi, Muhammad Muhyi Al-Din Abdul Hamid, Salim al-Hilali) with the repository's own reference to the source page. Bukhari and Muslim carry no grades in the file and none are added. | NEEDS_REVIEW - Contract validation 0 failures. The grades were NOT checked against the graders' printed works. **[LICENSE_REQUIRED]** | no | scripts/run_importer.py hadith-api-grades [--apply]; imports HIDDEN | 2026-10-01 | Confirm the right to redistribute these grades (or replace them with grades from a source whose terms allow it), spot-check against the graders' printed works, then mark verified and publish in Data & trust. The five collections are not loaded in the reader, so these records cite the collection and number without linking to hadith text. |
| **Sahih Muslim, English translation**<br>`hadith-muslim-english`<br>PyPI sahih-muslim 1.1.2 (translation bundled in the package) 1.1.2 | English reading layer for the hadith reader. | Commercially published translation; redistribution rights not established (LICENSE_REQUIRED) | Bundled in the PyPI package; translator/publisher permission not documented. | NEEDS_REVIEW - Aligned 1:1 with the Arabic narrations. **[LICENSE_REQUIRED]** | no | importer script | 2026-10-01 | Obtain permission from the translation's rights holder, then publish with scripts/apply_publication_policy.py after recording rights_confirmation in this entry. |
| **Qur'an translations, 482 further editions in 97 languages**<br>`quran-translations-catalogue`<br>fawazahmed0/quran-api catalogue (editions.json) branch 1 (retrieved 2026-09-30) | Optional extra translations once rights are confirmed. | No per-edition licence in the catalogue (LICENSE_REQUIRED) | raw.githubusercontent.com; each edition's sha256 recorded. | VERIFIED - Every stored edition has 6,236 verses, numbering identical to the Arabic, at least 99% non-empty. 1 edition failed (217 empty verses). **[LICENSE_REQUIRED]** | no | importer script | 2026-10-01 | For each edition you want public: confirm the publisher's/translator's permission, record it, then publish (scripts/publish_staged.py or this manifest). |
| **Arabic classical tafsirs (29 editions incl. al-Tabari, al-Qurtubi, al-Razi, Ibn Kathir, al-Jalalayn)**<br>`tafsir-arabic-classical`<br>spa5k/tafsir_api (data from Quran.com / Tarteel QUL / altafsir.com) branch main (retrieved 2026-09-30) | Scholarly explanation layer for the reader and assistant. | Original works are public domain; the digital editions' own rights are not stated (some carry modern editorial notes) (LICENSE_REQUIRED) | raw.githubusercontent.com. | VERIFIED - Each edition checked for Qur'an coverage and for alignment of entries to their ayah (quoted ayah or at least 60% word overlap, 80% of entries). Partial works are labelled with their coverage. **[LICENSE_REQUIRED]** | no | importer script | 2026-10-01 | Confirm the terms of the digital editions (QUL / Quran.com compilations) and strip modern editorial matter if required; then publish. |
| **Arabic modern tafsirs (16 editions incl. Ibn Ashur, Tantawi, al-Muyassar)**<br>`tafsir-arabic-modern`<br>spa5k/tafsir_api (data from Quran.com / Tarteel QUL / altafsir.com) branch main (retrieved 2026-09-30) | Scholarly explanation layer. | Modern works; rights not cleared (LICENSE_REQUIRED) | raw.githubusercontent.com. | VERIFIED - As above. **[LICENSE_REQUIRED]** | no | importer script | 2026-10-01 | Permission from each author's estate or publisher. |
| **English tafsirs (9 editions incl. Ibn Kathir (abridged), Ma'ariful Qur'an, Jalalayn, Tazkirul Quran)**<br>`tafsir-english`<br>spa5k/tafsir_api (data from Quran.com / Tarteel QUL / altafsir.com) branch main (retrieved 2026-09-30) | English scholarly explanation. | Modern translations; rights not cleared (LICENSE_REQUIRED) | raw.githubusercontent.com. | VERIFIED - As above. **[LICENSE_REQUIRED]** | no | importer script | 2026-10-01 | Permission from each translator or publisher. |
| **Morning and evening adhkar, Arabic**<br>`devotional-adhkar-arabic`<br>npm @kazishariar/morning-evening-adhkar-data 1.0.3 | Dhikr reader. | Package declares CC BY 4.0; upstream not documented (PROVENANCE_UNCLEAR) | npm package. | NEEDS_REVIEW - Arabic cross-check label per entry; source cited per entry. **[PROVENANCE_UNCLEAR]** | no | importer script | 2026-10-01 | Confirm upstream terms. |
| **Morning and evening adhkar, English**<br>`devotional-adhkar-english`<br>npm @kazishariar/morning-evening-adhkar-data (bundled translation) 1.0.3 | English layer. | Translator not documented (PROVENANCE_UNCLEAR) | npm package. | NEEDS_REVIEW - Not independently verified. **[PROVENANCE_UNCLEAR]** | no | importer script | 2026-10-01 | Identify the translator and obtain permission. |
| **Hisn al-Muslim (supplications), Arabic**<br>`devotional-hisn-almuslim-arabic`<br>npm @kazishariar/hisnul-muslim-data 1.0.3 | Dua and dhikr reader. | Package declares CC BY 4.0; upstream (selection, numbering, commentary) not documented (PROVENANCE_UNCLEAR) | npm package. | NEEDS_REVIEW - Per entry: 67 cross-checked against the Qur'an, 109 against Bukhari/Muslim, the rest not cross-checked and labelled as such. **[PROVENANCE_UNCLEAR]** | no | importer script | 2026-10-01 | Identify the upstream compilation and confirm its terms, or supply a licensed source. |
| **Forty Hadith of al-Nawawi, English**<br>`hadith-nawawi40-english`<br>npm @kazishariar/nawawi-40-hadith-data (bundled translation) 1.0.3 | English layer. | Translator and upstream not documented (PROVENANCE_UNCLEAR) | npm package. | NEEDS_REVIEW - Not independently verified. **[PROVENANCE_UNCLEAR]** | no | importer script | 2026-10-01 | Identify the translator and obtain permission, or supply an authorised translation. |
| **Aqeedah texts**<br>`aqeedah`<br>No source acquired | Creed texts and references. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_knowledge_records.py | 2026-10-01 | Supply licensed texts with authors and citations. |
| **Civilization and heritage**<br>`civilization`<br>No source acquired | Sourced civilization entries. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_knowledge_records.py | 2026-10-01 | Supply licensed sources. |
| **Businesses**<br>`directory-businesses`<br>No source acquired | Businesses directory. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_directory.py | 2026-10-01 | Supply an authorised business dataset or partner API. |
| **Charities**<br>`directory-charities`<br>No source acquired | Charities directory. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_directory.py | 2026-10-01 | Supply an authorised dataset, e.g. a national charity register published under an open government licence (verify the licence per country). |
| **Events**<br>`directory-events`<br>No source acquired | Events directory. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_directory.py | 2026-10-01 | Supply an events feed or use 'suggest a listing'. |
| **Health services**<br>`directory-health`<br>No source acquired | Health services directory. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_directory.py | 2026-10-01 | Supply an authorised dataset. |
| **Jobs**<br>`directory-jobs`<br>No source acquired | Jobs directory. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_directory.py | 2026-10-01 | Supply listings or an employer partnership. |
| **Organisations**<br>`directory-organisations`<br>No source acquired | Organisations directory. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_directory.py | 2026-10-01 | Supply an authorised dataset or use 'suggest a listing'. |
| **Professionals**<br>`directory-professionals`<br>No source acquired | Professionals directory. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_directory.py | 2026-10-01 | Professionals register themselves via 'suggest a listing' and are verified by moderators; or upload a dataset. |
| **Volunteering**<br>`directory-volunteering`<br>No source acquired | Volunteering directory. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_directory.py | 2026-10-01 | Supply opportunities or partner feed. |
| **Fiqh (rulings and madhhab positions)**<br>`fiqh-rulings`<br>No source acquired | Source-cited fiqh references. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_knowledge_records.py | 2026-10-01 | Supply licensed fiqh text/data with author, school and citation. The assistant never invents rulings. |
| **Islamic history**<br>`history`<br>No source acquired | Sourced historical entries. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_knowledge_records.py | 2026-10-01 | Supply licensed history sources. |
| **Library (books and works)**<br>`library-works`<br>No source acquired | Catalogue of classical works with edition and licence. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_knowledge_records.py | 2026-10-01 | Supply a catalogue with edition/licence per work, or a public-domain corpus whose licence has been verified. |
| **Scholar biographies**<br>`scholar-biographies`<br>No source acquired | Biographies with sources. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_knowledge_records.py | 2026-10-01 | Supply biographies with sources and licence. Wikipedia/Wikidata could not be reached from this environment, so none was imported. |
| **Seerah**<br>`seerah`<br>No source acquired | Source-cited biography of the Prophet. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_knowledge_records.py | 2026-10-01 | Supply licensed seerah sources (e.g. a public-domain translation with provenance). |
| **Islamic terminology**<br>`terminology`<br>No source acquired | Glossary with sources. | Not applicable (no data) (UNKNOWN) | No dataset is loaded; nothing is generated from model memory. | NOT_RUN - No data to validate. **[OWNER_UPLOAD_REQUIRED]** | no | admin upload or scripts/import_knowledge_records.py | 2026-10-01 | Supply a licensed glossary with a source per term. |

## Legitimate alternatives investigated

**Hadith grading**
- sunnah.com API requires a key and has its own terms; not accessed (host not reachable from the build environment).
- Packages sunan-abi-dawud, sunan-al-nasai, sunan-ibn-majah (AGPL-3.0 declared): see docs/SOURCE_VERIFICATION.md.

**Fiqh (rulings and madhhab positions)**
- npm @al-mabsut/muslimah (Hanafi guidance on women's issues, ISC declared for the package): not imported. The content has no cited work, edition or page, and no content licence file in the repository; the contract refuses fiqh without a traceable source.
- No other openly licensed, verifiable fiqh dataset was reachable from this environment.

**Aqeedah texts**
- No verifiable open dataset found.

**Seerah**
- OpenITI (Open Islamicate Texts Initiative) hosts classical Arabic texts. Its licence could not be read from the files reachable here, so it was not used; the owner should check its terms (it is understood to carry a non-commercial restriction) before importing anything.

**Library (books and works)**
- OpenITI (classical Arabic corpus and metadata): licence files and metadata could not be retrieved, so the licence is not established; not used.
- npm finding-islamic-books / islamic-books: random book-name lists without author, edition or licence; not a catalogue.

**Scholar biographies**
- Wikidata (CC0) and Wikipedia (CC BY-SA) are legitimate candidates but were unreachable here; use the data-contract importer on a machine that can reach them, keeping the per-record source URL.

**Mosques**
- OpenStreetMap via Overpass (ODbL) is the best open source for other regions; scripts/import_osm_mosques.py is ready but Overpass is not reachable from the build environment (checked 2026-10-01).
- Wikidata SPARQL (CC0) is not reachable from the build environment (checked 2026-10-01).

## How a dataset becomes public

1. Import it (a script, or an administrator upload to `/api/v1/admin/datasets/{id}/import`).
2. A person checks it and marks it verified (`mark_verified`, with a note).
3. If its licence is not clearly open, the owner records permission (who, when, basis) while publishing.
4. `scripts/sync_manifest.py` (or the admin *Sync manifest* action) applies the decision to readers, search, the assistant and the knowledge graph.
