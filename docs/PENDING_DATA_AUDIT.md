# Pending data audit

Audit of every domain against the actual repository and database on **2026-10-01**, repeated at the start of the readiness pass. It does not trust the previous report: each claim below was checked.

Statuses use the readiness vocabulary of [`DATA_READINESS.md`](DATA_READINESS.md); sources and licences are in [`SOURCE_VERIFICATION.md`](SOURCE_VERIFICATION.md). No human scholarly or legal review has taken place for any domain.

## Claims of the previous report, checked

| Claim | How it was checked | Result |
|---|---|---|
| 668 API unit/contract tests pass | Re-ran `pytest --ignore=tests/integration` on the restored environment before changing anything | CONFIRMED: 668 passed |
| 19,781 mosque listings, 19,776 visible, 5 duplicates hidden | SQL counts on the working database | CONFIRMED |
| 21,185 hadith gradings / 67,681 grader entries, hidden | SQL counts; public `/knowledge/records` returned 0 for the type | CONFIRMED (hidden) |
| 13 validation rules pass | Ran `scripts/validate_data.py` on the populated database | CONFIRMED (now 14 rules after this pass) |
| Admin preview, unpublish, provenance/history exist | Read `datasets_admin.py` and `admin-data-panel.tsx` | CONFIRMED in code; the screens had NOT been clicked through (done in this pass) |
| Browser checks passed on the production stack | The report said development server only | CONFIRMED as a limitation: production Docker/nginx verification had not been done (done in this pass) |
| Hadith gradings: Zubair Ali Za'i's references are 'named' in References.md | Re-read References.md | CONFIRMED: the file names zubairalizai.com with no page |
| Mosque anomaly: one former synagogue | Keyword scan of every imported name | INCOMPLETE: the scan found 7 more records with 'Chapel'/'Temple' in their names (see `data/source-quality-notes.json`); cause unknown |
| Domain status vocabulary (READY, PARTIALLY_READY, ...) | Compared with the requested vocabulary | REPLACED by EMPTY ... READY with twelve gates (`data/domain-readiness.json`) |
| Imports 'record the source version' | Read `DataSetImport` | NOT TRUE before this pass: only a file hash was stored. Migration 0087 adds adapter, source version, retrieval time and checksum |

## What exists

- **Migrations**: 87 (head `20261001_0087`): 0084 data contract and directories, 0085 Arabic full text, 0086 provenance and per-type structure, 0087 import source versions.
- **Source registry**: `Source` > `SourceEdition` (publisher, language, ISBN, licence) > acquisition > integrity > review > attribution > retrieval gate; claims with dispute notes; `data/source-manifest.json`; `data/source-candidates.json`; `data/domain-readiness.json`.
- **Importers**: source adapters in `app/importers` (GeoAlgeria mosques, hadith-api gradings, OpenStreetMap Overpass) run by `scripts/run_importer.py` or *Data & trust > Importers*; the contract importers `import_knowledge_records.py` / `import_directory.py`; the older Qur'an, hadith, tafsir and translation importers.
- **Admin**: readiness (why not READY), importers (probe, preview, run), datasets (preview, verify, publish, unpublish, provenance and import history with source versions, conflicts, rollback), directory moderation, reports, assistant answers, audit log.
- **Quality**: `scripts/validate_data.py` (14 rules), `scripts/data_quality_report.py` ([`DATA_QUALITY_REPORT.md`](DATA_QUALITY_REPORT.md)), conflict detection (`app/services/data_quality.py`), `data/source-quality-notes.json`.
- **Assistant**: retrieves approved Qur'an/hadith/tafsir evidence and published knowledge records; every item carries an authority class, verification state, source, edition, record id and URL; it abstains without a sufficient source.

## Per domain

### Qur'an

- **DOMAIN**: Qur'an (`quran`, tier 1)
- **STATUS**: READY (FULL coverage)
- **CURRENT_SCHEMA**: `quran_*` tables with source passages and checksums.
- **IMPORTER**: scripts/import_quran_reader.py, import_tajweed.py, import_translations.py
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 6236 ayahs (Arabic text) (6236 published, 0 hidden)
- **CURRENT_SOURCE**: PyPI quran-text (quran.ws, KFGQPC text) 0.1.0; fawazahmed0/quran-api for the two translations; npm @quran.ws/tajwid-* 0.1.0 (0.1.0)
- **LICENCE**: CC BY 4.0 (text, tajweed); public domain (Pickthall, d. 1936; Yusuf Ali 1934 edition, d. 1953)
- **BLOCKER**: none
- **CANDIDATES EXAMINED**: see the manifest entry
- **NEXT_ACTION**: None.

### Hadith

- **DOMAIN**: Hadith (`hadith`, tier 1)
- **STATUS**: RIGHTS_UNVERIFIED (PARTIAL coverage)
- **CURRENT_SCHEMA**: `hadith_*` tables with source passages and checksums.
- **IMPORTER**: scripts/import_hadith_reader.py
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 15110 narrations (14778 published, 332 hidden)
- **CURRENT_SOURCE**: PyPI sahih-al-bukhari 3.1.7, sahih-muslim 1.1.2; npm @kazishariar/nawawi-40-hadith-data 1.0.3 (3.1.7 / 1.1.2 / 1.0.3)
- **LICENCE**: Packagers declare AGPL-3.0 (Bukhari, Muslim) and CC BY 4.0 (Nawawi); the classical Arabic works are public domain
- **BLOCKER**: Owner must confirm the AGPL-3.0 position for redistributing the packaged Arabic text (does not affect the public-domain status of the original work).; Nawawi-40 upstream compilation is undocumented; 41 of 42 entries cross-checked verbatim against Bukhari/Muslim.; English translations: translator and publisher permission not documented.; Hisn al-Muslim and adhkar: upstream not documented.
- **CANDIDATES EXAMINED**: see the manifest entry
- **NEXT_ACTION**: Resolve the blockers above.

### Hadith gradings

- **DOMAIN**: Hadith gradings (`hadith_gradings`, tier 1)
- **STATUS**: RIGHTS_UNVERIFIED (PARTIAL coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/build_hadith_grading_records.py + import_knowledge_records.py
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 21185 hadith gradings (records; 67,681 grader entries) (0 published, 21185 hidden)
- **CURRENT_SOURCE**: fawazahmed0/hadith-api info.json, git tag 1 (tag 1 (sha256 cf1ced267ada8f606f95eb84e2b6ddfa87bfa2a6a9dd4cb2a5d9a8c1734f10fb))
- **LICENCE**: Unlicense (repository). Rights in the compiled grades are not established.
- **BLOCKER**: The Unlicense covers only the repository author's own work, not the graders' modern published works that the grades were compiled from.; Source sites' terms unreachable; the compilation method (scraping) is evidenced by file names.; Grades not compared with the graders' printed works.; The five graded collections are not loaded, so no record links to hadith text.
- **CANDIDATES EXAMINED**: see the manifest entry
- **NEXT_ACTION**: Resolve the blockers above.

### Tafsir

- **DOMAIN**: Tafsir (`tafsir`, tier 1)
- **STATUS**: RIGHTS_UNVERIFIED (PARTIAL coverage)
- **CURRENT_SCHEMA**: `tafsir_*` tables with source passages.
- **IMPORTER**: scripts/import_tafsir.py, import_tafsir_catalogue.py
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 182320 tafsir entries (0 published, 182320 hidden)
- **CURRENT_SOURCE**: spa5k/tafsir_api (data compiled from Quran.com / Tarteel QUL / altafsir.com) (branch main, retrieved 2026-09-30)
- **LICENCE**: Original classical works are public domain; the digital editions' own rights are not stated and modern works are in copyright
- **BLOCKER**: Rights of the digital editions are not established; modern works need permission from authors/estates/publishers.; Some editions carry modern editorial notes that would need stripping.
- **CANDIDATES EXAMINED**: see the manifest entry
- **NEXT_ACTION**: Resolve the blockers above.

### Fiqh

- **DOMAIN**: Fiqh (`fiqh`, tier 1)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 records (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No openly licensed, verifiable fiqh dataset found.; @al-mabsut/muslimah rejected: no cited work or page, no content licence.
- **CANDIDATES EXAMINED**: npm-al-mabsut-muslimah, owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Aqeedah

- **DOMAIN**: Aqeedah (`aqeedah`, tier 1)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 records (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No source found.
- **CANDIDATES EXAMINED**: owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Seerah

- **DOMAIN**: Seerah (`seerah`, tier 1)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 records (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No source found; OpenITI licence not established.
- **CANDIDATES EXAMINED**: openiti, owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Scholar biographies

- **DOMAIN**: Scholar biographies (`scholars`, tier 1)
- **STATUS**: SOURCE_BLOCKED (NONE coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 records (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: Wikidata (CC0) is the intended open source but is unreachable from the build environment (2026-10-01).; OpenITI licence not established.
- **CANDIDATES EXAMINED**: wikidata, openiti, owner-supplied
- **NEXT_ACTION**: Resolve the blockers above.

### Islamic terminology

- **DOMAIN**: Islamic terminology (`terminology`, tier 1)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 records (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No source found.
- **CANDIDATES EXAMINED**: owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Islamic history

- **DOMAIN**: Islamic history (`history`, tier 2)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 records (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No source found.
- **CANDIDATES EXAMINED**: owner-supplied, openiti
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Islamic civilization

- **DOMAIN**: Islamic civilization (`civilization`, tier 2)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 records (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No source found.
- **CANDIDATES EXAMINED**: owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Libraries, books and catalogues

- **DOMAIN**: Libraries, books and catalogues (`libraries`, tier 2)
- **STATUS**: SOURCE_BLOCKED (NONE coverage)
- **CURRENT_SCHEMA**: `knowledge_records` with source-level provenance (migration 0086: work, edition, volume, page, chapter, language, publication/licence/provenance status, per-type `attributes`).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 records (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: Open Library, Internet Archive, Gutenberg, Wikidata unreachable (2026-10-01).; OpenITI licence not established.; PyPI 'hadith' (Umma1) bundles unattributed Arabic collections: provenance unclear.
- **CANDIDATES EXAMINED**: open-library-catalogues, wikidata, openiti, pypi-hadith-umma1
- **NEXT_ACTION**: Resolve the blockers above.

### Mosques

- **DOMAIN**: Mosques (`mosques`, tier 3)
- **STATUS**: PUBLISHED (PARTIAL coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: app/importers (geoalgeria-mosquees adapter), scripts/run_importer.py, scripts/import_osm_mosques.py
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 19781 listings (19776 published, 5 hidden)
- **CURRENT_SOURCE**: GeoAlgeria @geoalgeria/mosquees 2.0.4 (composite of Wikidata and OpenStreetMap) (2.0.4 (data built 2026-06-25))
- **LICENCE**: ODbL 1.0 (OpenStreetMap-derived records) and CC0-1.0 (Wikidata records); package code MIT
- **BLOCKER**: Algeria only.; Community composite, not an official registry; individual mosques are not verified in person.; Known source-quality anomalies are retained unchanged (e.g. a former synagogue classified as a mosque by Wikidata); see data/source-quality-notes.json.
- **CANDIDATES EXAMINED**: see the manifest entry
- **NEXT_ACTION**: Resolve the blockers above.

### Organisations

- **DOMAIN**: Organisations (`organisations`, tier 3)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 listings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No source reachable or found; Wikidata and OpenStreetMap unreachable.
- **CANDIDATES EXAMINED**: wikidata, openstreetmap-overpass, owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Events

- **DOMAIN**: Events (`events`, tier 3)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 listings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: Organiser-supplied only; Hijri calendar libraries carry no cited authority.
- **CANDIDATES EXAMINED**: npm-islamic-calendar-events, owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Charities

- **DOMAIN**: Charities (`charities`, tier 3)
- **STATUS**: SOURCE_BLOCKED (NONE coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 listings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: National charity registers unreachable (2026-10-01).; A register does not say whether a charity is Muslim.
- **CANDIDATES EXAMINED**: official-charity-registers, owner-supplied
- **NEXT_ACTION**: Resolve the blockers above.

### Volunteering

- **DOMAIN**: Volunteering (`volunteering`, tier 3)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 listings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No source.
- **CANDIDATES EXAMINED**: owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Businesses

- **DOMAIN**: Businesses (`businesses`, tier 4)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 listings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No open dataset identifies Muslim-owned businesses.
- **CANDIDATES EXAMINED**: owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Professionals

- **DOMAIN**: Professionals (`professionals`, tier 4)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 listings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: Self-registration with moderation is the legitimate route; none registered.
- **CANDIDATES EXAMINED**: owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Health services

- **DOMAIN**: Health services (`health`, tier 4)
- **STATUS**: EMPTY (NONE coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 listings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: No source.
- **CANDIDATES EXAMINED**: owner-supplied
- **NEXT_ACTION**: Owner supplies an authorised dataset, or a legitimate source is found and its adapter written.

### Jobs

- **DOMAIN**: Jobs (`jobs`, tier 4)
- **STATUS**: SOURCE_BLOCKED (NONE coverage)
- **CURRENT_SCHEMA**: `directory_listings` with per-type `attributes`, expiry and start/end times (migration 0086).
- **IMPORTER**: scripts/import_knowledge_records.py (contract importer; all-or-nothing, preview, rollback)
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 listings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: Job APIs unreachable and need keys and terms acceptance (2026-10-01).
- **CANDIDATES EXAMINED**: job-feeds, owner-supplied
- **NEXT_ACTION**: Resolve the blockers above.

### Recitation audio

- **DOMAIN**: Recitation audio (`recitation_audio`, tier 5)
- **STATUS**: SOURCE_BLOCKED (NONE coverage)
- **CURRENT_SCHEMA**: `quran_recitation_editions` (hosted or external link, licence, authorisation, caching/offline flags) and `quran_ayah_audio`.
- **IMPORTER**: Admin API POST /quran/admin/recitations
- **ADMIN_WORKFLOW**: Data & trust (readiness, importers, datasets, conflicts, provenance and history, publish/unpublish, rollback)
- **API**: `/knowledge/domains`, `/knowledge/records`, `/directory/*`, `/quran/*`, `/hadith/*`, `/tafsir/*`, `/search`, `/assistant/query`
- **CURRENT_DATA_COUNT**: 0 recordings (0 published, 0 hidden)
- **CURRENT_SOURCE**: none acquired
- **LICENCE**: not applicable
- **BLOCKER**: Recitation hosts unreachable from the build environment (everyayah.com, mp3quran.net, api.quran.com, cdn.islamic.network; 2026-10-01).; Reciter and publisher redistribution terms not documented in an accessible form.
- **CANDIDATES EXAMINED**: quran-recitation-sources, npm-mp3quran-wrappers
- **NEXT_ACTION**: Resolve the blockers above.

## Gaps found and closed in this pass

1. No machine-readable domain readiness: added `data/domain-readiness.json`, twelve gates, a validator, a live evaluator that lowers a status the data no longer supports, `/knowledge/domains`, an admin view with the reason for every non-READY domain, and an honest public dashboard.
2. Importers were ad-hoc scripts: replaced by a source-adapter architecture with probes, preview, all-or-nothing runs, version and checksum recording, and safe re-runs.
3. Hadith grade entries had no place for the grading work, edition, page, rights or verification state: added (all optional, never inferred), keeping each grader separate.
4. Mosque data lacked source identifiers in a first-class place, coverage statements, and conflict reports: added the GeoAlgeria id, a coverage endpoint and UI statement, and duplicate/similar/co-located/non-mosque-name candidates (reported, never corrected).
5. The assistant treated every record alike: every cited item now carries an authority class and verification state.
6. No data-quality report and no Arabic review list: added both.
7. The admin screens had not been exercised in a browser and production Docker/nginx verification had not been done: see the final report for what was and was not verified.
