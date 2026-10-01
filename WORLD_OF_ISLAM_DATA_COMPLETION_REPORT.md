# World of Islam: data readiness report

Date: 2026-10-01. Branch `claude/world-of-islam-webapp-9rfzue`.

**The project is not data-complete, and this report does not say it is.** One domain is READY for a stated, limited scope (the Qur'an: Arabic text, tajweed, two public-domain English translations). One more is published with open gates (mosques, Algeria only). Three have real data that must stay hidden or is flagged because rights are not established. Twelve are EMPTY and five are SOURCE_BLOCKED. Nothing was written from memory, no record was invented, renamed or corrected, and no source was used whose licence and provenance could not be read.

Status vocabulary: EMPTY, SOURCE_BLOCKED, SOURCE_UNVERIFIED, RIGHTS_UNVERIFIED, IMPORT_READY, IMPORTED, VALIDATED, PUBLISHED, READY. READY needs all twelve gates ([`DATA_READINESS.md`](docs/DATA_READINESS.md)); an importer existing, records being present or a dataset being published is not enough. Nothing has had a human scholarly or legal review: every "verified" below means *checked by automated tests and by the assistant that built it*.

## DATA COMPLETION

| DOMAIN | STATUS | SOURCE | LICENCE | RECORD COUNT | PUBLISHED | HIDDEN | VALIDATION | PROVENANCE | BLOCKER | VERIFIED BY |
|---|---|---|---|---|---|---|---|---|---|---|
| Qur'an | **READY** (FULL) | PyPI quran-text (quran.ws, KFGQPC text) 0.1.0; fawazahmed0/quran-api for the two translations; npm @quran.ws/tajwid-* 0.1.0 | CC BY 4.0 (text, tajweed); public domain (Pickthall, d. 1936; Yusuf Ali 1934 edition, d. 1953) | 6236 | 6236 | 0 | VERIFIED | confidence high; recorded per record | none | Claude Code automated checks, 2026-10-01 (no human review) |
| Hadith | **RIGHTS_UNVERIFIED** (PARTIAL) | PyPI sahih-al-bukhari 3.1.7, sahih-muslim 1.1.2; npm @kazishariar/nawawi-40-hadith-data 1.0.3 | Packagers declare AGPL-3.0 (Bukhari, Muslim) and CC BY 4.0 (Nawawi); the classical Arabic works are public domain | 15110 | 14778 | 332 | NEEDS_REVIEW | confidence medium; recorded per record | Owner must confirm the AGPL-3.0 position for redistributing the packaged Arabic text (does not affect the public-domain status of the original work).; Nawawi-40 upstream compilation is undocumented; 41 of 42 entries cross-checked verbatim against Bukhari/Muslim.; English translations: translator and publisher permission not documented.; Hisn al-Muslim and adhkar: upstream not documented. | Claude Code automated checks, 2026-10-01 (no human review) |
| Hadith gradings | **RIGHTS_UNVERIFIED** (PARTIAL) | fawazahmed0/hadith-api info.json, git tag 1 | Unlicense (repository). Rights in the compiled grades are not established. | 21185 | 0 | 21185 | NEEDS_REVIEW | confidence medium; recorded per record | The Unlicense covers only the repository author's own work, not the graders' modern published works that the grades were compiled from.; Source sites' terms unreachable; the compilation method (scraping) is evidenced by file names.; Grades not compared with the graders' printed works.; The five graded collections are not loaded, so no record links to hadith text. | Claude Code automated checks, 2026-10-01 (no human review) |
| Tafsir | **RIGHTS_UNVERIFIED** (PARTIAL) | spa5k/tafsir_api (data compiled from Quran.com / Tarteel QUL / altafsir.com) | Original classical works are public domain; the digital editions' own rights are not stated and modern works are in copyright | 182320 | 0 | 182320 | VERIFIED | confidence medium; recorded per record | Rights of the digital editions are not established; modern works need permission from authors/estates/publishers.; Some editions carry modern editorial notes that would need stripping. | Claude Code automated checks, 2026-10-01 (no human review) |
| Fiqh | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No openly licensed, verifiable fiqh dataset found.; @al-mabsut/muslimah rejected: no cited work or page, no content licence. | Claude Code automated checks, 2026-10-01 (no human review) |
| Aqeedah | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No source found. | Claude Code automated checks, 2026-10-01 (no human review) |
| Seerah | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No source found; OpenITI licence not established. | Claude Code automated checks, 2026-10-01 (no human review) |
| Scholar biographies | **SOURCE_BLOCKED** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | Wikidata (CC0) is the intended open source but is unreachable from the build environment (2026-10-01).; OpenITI licence not established. | Claude Code automated checks, 2026-10-01 (no human review) |
| Islamic terminology | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No source found. | Claude Code automated checks, 2026-10-01 (no human review) |
| Islamic history | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No source found. | Claude Code automated checks, 2026-10-01 (no human review) |
| Islamic civilization | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No source found. | Claude Code automated checks, 2026-10-01 (no human review) |
| Libraries, books and catalogues | **SOURCE_BLOCKED** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | Open Library, Internet Archive, Gutenberg, Wikidata unreachable (2026-10-01).; OpenITI licence not established.; PyPI 'hadith' (Umma1) bundles unattributed Arabic collections: provenance unclear. | Claude Code automated checks, 2026-10-01 (no human review) |
| Mosques | **PUBLISHED** (PARTIAL) | GeoAlgeria @geoalgeria/mosquees 2.0.4 (composite of Wikidata and OpenStreetMap) | ODbL 1.0 (OpenStreetMap-derived records) and CC0-1.0 (Wikidata records); package code MIT | 19781 | 19776 | 5 | VERIFIED | confidence high; recorded per record | Algeria only.; Community composite, not an official registry; individual mosques are not verified in person.; Known source-quality anomalies are retained unchanged (e.g. a former synagogue classified as a mosque by Wikidata); see data/source-quality-notes.json. | Claude Code automated checks, 2026-10-01 (no human review) |
| Organisations | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No source reachable or found; Wikidata and OpenStreetMap unreachable. | Claude Code automated checks, 2026-10-01 (no human review) |
| Events | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | Organiser-supplied only; Hijri calendar libraries carry no cited authority. | Claude Code automated checks, 2026-10-01 (no human review) |
| Charities | **SOURCE_BLOCKED** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | National charity registers unreachable (2026-10-01).; A register does not say whether a charity is Muslim. | Claude Code automated checks, 2026-10-01 (no human review) |
| Volunteering | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No source. | Claude Code automated checks, 2026-10-01 (no human review) |
| Businesses | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No open dataset identifies Muslim-owned businesses. | Claude Code automated checks, 2026-10-01 (no human review) |
| Professionals | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | Self-registration with moderation is the legitimate route; none registered. | Claude Code automated checks, 2026-10-01 (no human review) |
| Health services | **EMPTY** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | No source. | Claude Code automated checks, 2026-10-01 (no human review) |
| Jobs | **SOURCE_BLOCKED** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | Job APIs unreachable and need keys and terms acceptance (2026-10-01). | Claude Code automated checks, 2026-10-01 (no human review) |
| Recitation audio | **SOURCE_BLOCKED** | - | - | 0 | 0 | 0 | NOT_RUN | confidence none; no records | Recitation hosts unreachable from the build environment (everyayah.com, mp3quran.net, api.quran.com, cdn.islamic.network; 2026-10-01).; Reciter and publisher redistribution terms not documented in an accessible form. | Claude Code automated checks, 2026-10-01 (no human review) |

Machine-readable: [`data/domain-summary.json`](data/domain-summary.json) (generated from the live database by `scripts/export_domain_summary.py`), registry [`data/domain-readiness.json`](data/domain-readiness.json), live dashboard `GET /knowledge/domains` and the *Status* page.

## The five evidence classes, kept apart

### VERIFIED (checked in this pass)

- Qur'an: Every ayah's text matches its recorded sha256 and traces to an approved source edition (validate_data.py)
- Qur'an: CC BY 4.0 licence of quran-text read from PyPI metadata (2026-10-01)
- Qur'an: 6,236 ayahs published (database count)
- Qur'an: Assistant query returns Qur'an passages with source, licence and authority class (live check)
- Hadith: Bukhari and Muslim hadith 1 wording matches the expected text
- Hadith: Counts: 15,110 narrations, 14,778 published (database)
- Hadith: Nawawi-40: 41 of 42 entries found verbatim in Bukhari/Muslim
- Hadith gradings: Contract validation: 21,185 records, 0 failures
- Hadith gradings: Each grader's grade is stored separately; none inferred
- Hadith gradings: Repository LICENSE read verbatim (Unlicense); References.md read
- Tafsir: Per-edition coverage and ayah alignment checks (import time)
- Tafsir: 182,320 entries hidden (database count)
- Fiqh: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Aqeedah: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Seerah: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Scholar biographies: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Islamic terminology: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Islamic history: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Islamic civilization: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Libraries, books and catalogues: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Mosques: Package LICENSE and dataset-metadata read (ODbL + CC0)
- Mosques: Download integrity (sha512) and tarball sha256 recorded
- Mosques: All coordinates inside Algeria's bounding box; ids unique; validate_data.py passes
- Mosques: Source identifiers preserved on every listing
- Organisations: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Events: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Charities: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Volunteering: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Businesses: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Professionals: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Health services: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Jobs: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain
- Recitation audio: Importer, validators and empty state exist and are tested; the database holds 0 records for this domain

### IMPORTED (present in the database)

- Qur'an: 6,236 ayahs (Arabic)
- Qur'an: Pickthall and Yusuf Ali (1934) translations
- Qur'an: tajweed rules and spans
- Hadith: Bukhari 7,277
- Hadith: Muslim 7,459
- Hadith: Nawawi-40 42
- Hadith: Hisn al-Muslim and adhkar 332 (hidden)
- Hadith gradings: 21,185 records / 67,681 grader entries (hidden)
- Tafsir: 54 editions, 182,320 entries (hidden)
- Mosques: 19,781 listings (19,776 visible)

### UNVERIFIED (not checked by anyone)

- Qur'an: Arabic wording against a printed mushaf by a person
- Qur'an: Translation accuracy
- Hadith: Redistribution rights of the packaged Arabic text (AGPL-3.0 declared)
- Hadith: English translations' rights
- Hadith: Nawawi-40 upstream
- Hadith gradings: Rights in the compiled grades
- Hadith gradings: Accuracy against the graders' printed works
- Hadith gradings: Whether short grade labels are protected
- Tafsir: Rights of every edition
- Tafsir: Absence of modern editorial notes
- Mosques: Each mosque's existence and details
- Mosques: Commune assignment (derived by the source)
- Mosques: Records flagged by the conflict check (282 co-located different names, 38 similar names, 8 non-mosque names)

### ASSUMED (taken on trust)

- Qur'an: Public-domain status of the two translations in every jurisdiction
- Qur'an: Fidelity of the upstream text beyond sha256 consistency
- Hadith: Public-domain status of the classical Arabic originals
- Hadith: Numbering and diacritics of the packaged editions
- Hadith gradings: Grades are as the repository states them
- Tafsir: Attribution of each edition as the repository states it
- Mosques: That the platform's directory needs only attribution for ODbL (share-alike may apply)
- Mosques: Upstream OSM/Wikidata accuracy

### BLOCKED

- Hadith: Rights decision by the owner
- Hadith gradings: al-maktaba.org, zubairalizai.com terms unreachable
- Tafsir: Rights of digital editions
- Fiqh: No openly licensed, verifiable fiqh dataset found.
- Fiqh: @al-mabsut/muslimah rejected: no cited work or page, no content licence.
- Aqeedah: No source found.
- Seerah: No source found; OpenITI licence not established.
- Scholar biographies: Wikidata (CC0) is the intended open source but is unreachable from the build environment (2026-10-01).
- Scholar biographies: OpenITI licence not established.
- Islamic terminology: No source found.
- Islamic history: No source found.
- Islamic civilization: No source found.
- Libraries, books and catalogues: Open Library, Internet Archive, Gutenberg, Wikidata unreachable (2026-10-01).
- Libraries, books and catalogues: OpenITI licence not established.
- Libraries, books and catalogues: PyPI 'hadith' (Umma1) bundles unattributed Arabic collections: provenance unclear.
- Mosques: No source for other countries reachable
- Organisations: No source reachable or found; Wikidata and OpenStreetMap unreachable.
- Events: Organiser-supplied only; Hijri calendar libraries carry no cited authority.
- Charities: National charity registers unreachable (2026-10-01).
- Charities: A register does not say whether a charity is Muslim.
- Volunteering: No source.
- Businesses: No open dataset identifies Muslim-owned businesses.
- Professionals: Self-registration with moderation is the legitimate route; none registered.
- Health services: No source.
- Jobs: Job APIs unreachable and need keys and terms acceptance (2026-10-01).
- Recitation audio: Recitation hosts unreachable from the build environment (everyayah.com, mp3quran.net, api.quran.com, cdn.islamic.network; 2026-10-01).
- Recitation audio: Reciter and publisher redistribution terms not documented in an accessible form.

## ENGINEERING

- **tests**: 724 passed (706 unit/contract + 18 integration against a real PostgreSQL database, run repeatedly); 43 web unit tests. New: `tests/test_readiness_and_importers.py` (36 tests: registry overclaim rejection, live downgrade, authority classes, adapters, licence refusal, per-grade fields, conflicts, determinism), integration tests for the importer lifecycle (preview, fail-safe, run, idempotent re-run, version/checksum recorded, rollback), the dashboard, scoped publication policy and the assistant's authority fields.
- **data validation**: `scripts/validate_data.py` 14 of 14 rules pass on the populated database, including the new rule that the readiness registry agrees with the manifest and the live counts.
- **typecheck**: `tsc --noEmit` clean. `mypy app`: only the four pre-existing missing-stub notices for `boto3`.
- **lint**: ESLint clean; `ruff --select F,B` clean on every new and changed module.
- **build**: `next build` with `WOI_BASE_PATH=/worldofislam` succeeds; the production API and web images (from the repository's Dockerfiles) were built and run.
- **migrations**: 87 migrations; upgrade, downgrade to base, upgrade again on an empty database gives identical schemas (3,492 columns); 0086 and 0087 also ran on copies of the populated database and inside the production image.
- **production Docker/nginx browser checks**: 53 of 53 checks pass in real Chromium against the production API and web images behind nginx with TLS at `https://woi.test/worldofislam` ([`infrastructure/verify/`](infrastructure/verify/)). **Not the full production compose file**: MinIO, Ollama, the Celery worker and the backup job were not run (Docker Hub rate-limited the build host and `quay.io` is blocked), the images were built from copies of the Dockerfiles that pull base images from a mirror, the database was a restored copy of the working database, and the certificate is self-signed.
- **Arabic RTL**: verified on `/ar/status`, `/ar/directory`, `/ar/knowledge/fiqh` and `/ar/quran/1` (RTL, no horizontal scroll, dashboard in Arabic, exact Arabic empty state). The Arabic wording itself is **not reviewed**: [`docs/ARABIC_QA.md`](docs/ARABIC_QA.md) lists all 137 strings added since the previous phase (12 flagged as religious terms), every one `NEEDS_NATIVE_REVIEW`. Registry text (scope, blockers) is English only.
- **mobile**: 390 px wide, English and Arabic: no horizontal scroll on the status, directory, knowledge and Qur'an pages (after fixing the status table).
- **base path**: every check ran under `/worldofislam` through nginx, including the icon, the manifest and the API.
- **admin workflow**: clicked through in Chromium: sign in; readiness tab with the reason each domain is not READY; importers tab (reachability check, a preview of an unreachable source fails safely with a message); upload with an invalid row (preview shows the error, Import disabled); corrected file; import; publish refused before verification; verify; publish; only the open job is public and the expired one is not; duplicates and conflicts panel; unpublish removes it at once; provenance and import history; rollback; a finished event stays excluded while the upcoming one shows; the audit log records every action. Test rows were labelled fixtures and exist only in the verification database.
- **console and network**: 18 expected 401s (anonymous visitors asking for a CSRF token and preferences), 1 expected 502 (the deliberate unreachable-source preview), 1 expected 409 (publish before verify), 1 403 that the client recovered from (below), aborted Next.js prefetches, and the service worker failing to register because of the self-signed certificate. No page error.

### Defects found by running the real images, and fixed

1. `manifest_path()` raised `IndexError` inside the container (the module is too shallow for `parents[4]`): every manifest, registry and domain endpoint returned 500 in the production image. Fixed with a test of the container layout.
2. Every dataset action rewrote all rows of every large table (182,320 tafsir entries, 3 million translation rows, graph tables): minutes per click on a populated database, with concurrent clicks piling up. The policy now writes only rows that differ and an action is scoped to its own dataset (full pass 14 s, one dataset under a second, identical end state).
3. A second browser tab invalidated the first tab's CSRF token (writes failed with 403). The client now fetches the current token and retries once; tested.
4. The status table made `/status` scroll sideways on phones (grid items had no `min-width: 0`).
5. Browsers asked for a missing `/favicon.ico` on every page.
6. Cited passages showed their attribution text but not the licence name; the licence name is now included.

## What was built

- **Readiness registry**: `data/domain-readiness.json` (22 domains, twelve gates with evidence, blockers, confidences, coverage, five evidence classes), validator, live evaluator that lowers a status the data no longer supports, public dashboard, admin view with the reason for every non-READY domain.
- **Source adapters** (`app/importers`): GeoAlgeria mosques, hadith-api gradings (hidden), OpenStreetMap Overpass (any area; blocked from here). `scripts/run_importer.py` and *Data & trust > Importers*: probe, preview, all-or-nothing run, safe re-run, source version, retrieval time and checksum recorded (migration 0087).
- **Hadith gradings**: per-grade fields for grading work, edition, page, source reference text, rights status and verification status (all optional, never inferred); the repository's References.md line is kept verbatim on every grade; 21,185 records re-imported through the adapter and kept hidden.
- **Mosques**: source identifiers preserved (GeoAlgeria id, Wikidata, OSM); coverage endpoint and a visible statement that only Algeria has data; conflict report (duplicates, similar names, co-located different names, non-mosque names); `data/source-quality-notes.json` retaining the anomalies unchanged.
- **Assistant**: every cited item carries an authority class (`primary_source`, `secondary_source`, `community_dataset`, `unverified`, `disputed`, `inferred`, `unavailable`), verification state, source title, author, edition, record id and URL; abstention is marked unavailable.
- **Quality and review aids**: `scripts/data_quality_report.py` ([`docs/DATA_QUALITY_REPORT.md`](docs/DATA_QUALITY_REPORT.md)), the Arabic QA checklist, `data/source-candidates.json` with evidence and unresolved questions for 21 candidates (including the PyPI and npm discovery scans).

## Source discovery

Scanned all 903,694 PyPI project names and about 40 npm searches, then read the licence and contents of every data-bearing candidate. New this pass: `hadith` (Umma Open Source: unattributed Arabic collections, provenance unclear, not imported), `openiti` on PyPI (code MIT, corpus licence still not stated; the repository README, LICENSE and Zenodo are unreachable or silent). The three sources rejected before remain rejected. No new usable dataset was found for fiqh, aqeedah, seerah, scholars, terminology, history, civilization or libraries.

## Hadith gradings: what the investigation found

The Unlicense in `fawazahmed0/hadith-api` dedicates only the repository author's own work. `References.md` shows the grades were taken from al-maktaba.org books and zubairalizai.com; the `database/originals/*scrapped.txt` file names show scraping; none of those sites is reachable to read its terms. The grades are short factual judgements by named modern scholars, compiled systematically (about 21,000 hadiths, 67,681 entries): whether that is protected expression, a database right, or free to republish is a legal question this project did not settle. They stay hidden (RIGHTS_UNVERIFIED), differing graders are kept side by side, and no grade is shown as verified.

## REMAINING BLOCKERS

Only real ones:

1. **Hadith gradings**: rights in the compiled grades; accuracy against the printed works.
2. **Hadith (published Arabic text)**: the owner's decision on the packagers' AGPL-3.0 declaration and the undocumented Nawawi-40 upstream; English translations' rights.
3. **Tafsir (182,320 entries, hidden)**: rights of every digital edition.
4. **Owner data** for fiqh, aqeedah, seerah, terminology, history, civilization, organisations, events, volunteering, businesses, professionals, health.
5. **Sources unreachable from the build environment**: Wikidata (scholars, libraries), Open Library/Internet Archive/Gutenberg, charity registers, job APIs, recitation hosts, OpenStreetMap Overpass (other countries), sunnah.com. They may be reachable from the production server; the probe in *Data & trust > Importers* tells the administrator. Their licences have not been assessed.
6. **Native Arabic review** of the strings in `docs/ARABIC_QA.md`.
7. **Mosque data accuracy**: every listing is unverified; 8 name anomalies, 282 co-located different names and 38 near-identical names await human review.

## DO NOT CLAIM

- That any domain's content has been reviewed by a scholar or a lawyer: none has.
- That the Qur'an domain is complete beyond its stated scope: 482 further translations are hidden and recitation audio does not exist; its READY rests on automated checks, the licence text read on PyPI, and the assumption that the two translations are public domain where the platform is used.
- That the mosque directory is global, verified, or free of errors.
- That the production compose file (`docker-compose.prod.yml`) was started: it could not be (no MinIO, Ollama or worker image). MinIO-backed integrity storage, Ollama, the worker and backups are unverified in this pass.
- That the importers can reach their sources from the production server: only the GeoAlgeria and hadith-api importers were run (from the build host); the Overpass importer has only been tested on the Overpass JSON shape.
- That the Arabic interface text is correct.
- That the ODbL share-alike obligation is satisfied by attribution alone (it may apply to the derived directory database).
