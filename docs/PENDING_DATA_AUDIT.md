# Pending data audit

**Phase 1 of the data-completion work.** An audit of every pending domain as the repository stood *before* any data was acquired in this phase, so that nothing already built was rebuilt. Counts were read from the working database on 2026-10-01 (`knowledge_records` 0, `directory_listings` 1 test row that is not shipped data, `hadith_gradings` 0, `quran_ayah_audio` 0).

Final results are in [`DATA_READINESS.md`](DATA_READINESS.md) and [`SOURCE_VERIFICATION.md`](SOURCE_VERIFICATION.md); the closing report is `WORLD_OF_ISLAM_DATA_COMPLETION_REPORT.md`.

## What existed (all domains)

- **Migrations**: 85 (head `20261001_0085`). `0084` created the data contract and directory tables; `0085` Arabic full-text.
- **Source registry and manifest**: `data/source-manifest.json` (36 datasets, each with source, licence, provenance, validation, publication, readiness, remaining action), `app/services/manifest.py`, `publication_policy.py`.
- **Contracts and validation**: `app/services/data_contracts.py`, `data_validation.py`, `scripts/validate_data.py` (9 rules).
- **Empty-state components**: `lib/copy.ts` (`NOT_PUBLIC`, `READINESS_LABEL`), `knowledge-browser.tsx`, `directory-browser.tsx`, `/status`.
- **Tests**: `tests/test_data_contracts.py`, `test_data_validation.py`, `test_osm_import.py`, `tests/integration/test_api_integration.py`.

## Per domain

The status after this phase is shown last, for orientation; the other fields describe the state found.

### Fiqh

- **DOMAIN**: Fiqh (`fiqh-rulings`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `fiqh`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=fiqh`.
- **FRONTEND**: `/[locale]/knowledge/fiqh` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No openly licensed, verifiable fiqh dataset reachable. @al-mabsut/muslimah checked: no cited work or page, no content licence.
- **NEXT_ACTION**: Owner supplies licensed fiqh with madhhab, author, work and page.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Aqeedah

- **DOMAIN**: Aqeedah (`aqeedah`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `aqeedah`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=aqeedah`.
- **FRONTEND**: `/[locale]/knowledge/aqeedah` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No source found.
- **NEXT_ACTION**: Owner supplies licensed texts with school, author and citation.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Seerah

- **DOMAIN**: Seerah (`seerah`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `seerah`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=seerah`.
- **FRONTEND**: `/[locale]/knowledge/seerah` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No source found; OpenITI's licence could not be established.
- **NEXT_ACTION**: Owner supplies a sourced chronology with reliability categories.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Hadith grading

- **DOMAIN**: Hadith grading (`hadith-grading`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `hadith_grading`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=hadith_grading`.
- **FRONTEND**: `/[locale]/knowledge/hadith_grading` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Candidate found (fawazahmed0/hadith-api); rights in the compiled grades not established.
- **NEXT_ACTION**: Confirm rights, spot-check, publish.
- **Status after this phase**: NEEDS_LICENSE

### Islamic terminology

- **DOMAIN**: Islamic terminology (`terminology`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `terminology`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=terminology`.
- **FRONTEND**: `/[locale]/knowledge/terminology` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No source found.
- **NEXT_ACTION**: Owner supplies a licensed glossary.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Islamic library

- **DOMAIN**: Islamic library (`library-works`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `library_work`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=library_work`.
- **FRONTEND**: `/[locale]/knowledge/library_work` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Open catalogues (Open Library, Wikidata) unreachable; OpenITI licence unestablished.
- **NEXT_ACTION**: Run a catalogue importer where the hosts are reachable, or supply a catalogue.
- **Status after this phase**: SOURCE_UNAVAILABLE

### Islamic history

- **DOMAIN**: Islamic history (`history`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `history`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=history`.
- **FRONTEND**: `/[locale]/knowledge/history` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No source found.
- **NEXT_ACTION**: Owner supplies sourced entries.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Islamic civilization

- **DOMAIN**: Islamic civilization (`civilization`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `civilization`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=civilization`.
- **FRONTEND**: `/[locale]/knowledge/civilization` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No source found.
- **NEXT_ACTION**: Owner supplies sourced entries.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Scholar biographies

- **DOMAIN**: Scholar biographies (`scholar-biographies`)
- **CURRENT_SCHEMA**: `knowledge_records` (entity_type `scholar`): id, title, arabic_title, description, source, source_url, author, date, licence, provenance, scholarly_status, confidence, last_verified, tags, relationships. No work/edition/volume/page/chapter/language, no per-type structure.
- **IMPORTER**: `scripts/import_knowledge_records.py` (contract importer, idempotent, rollback). Partial imports were allowed.
- **ADMIN_WORKFLOW**: `/api/v1/admin/datasets/*` + web `Data & trust`: list, manifest sync, verify, publish, stage, disable, reject, upload, import list, rollback, audit log. No preview, no unpublish, no provenance view.
- **API**: `GET /knowledge/readiness`, `/knowledge/records`, `/knowledge/records/{dataset}/{id}`, `/search?types=scholar`.
- **FRONTEND**: `/[locale]/knowledge/scholar` (browser, search, provenance card, honest empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `knowledge_records`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Wikidata unreachable; OpenITI unestablished.
- **NEXT_ACTION**: Import from Wikidata (CC0) where reachable, or supply biographies.
- **Status after this phase**: SOURCE_UNAVAILABLE

### Qur'an recitation audio

- **DOMAIN**: Qur'an recitation audio (`audio-quran-recitations`)
- **CURRENT_SCHEMA**: `quran_recitation_editions` (reciter, riwayah, format, attribution, published) and `quran_ayah_audio` (URL, sha256, size and duration all required). No licence, authorisation, external-link, caching or offline fields.
- **IMPORTER**: None (admin API only).
- **ADMIN_WORKFLOW**: `POST /quran/admin/recitations`, add audio, publish (needs an approved source edition).
- **API**: `GET /quran/recitations`, `/quran/surahs/{n}/audio`, playback progress.
- **FRONTEND**: Qur'an reader: reciter selector and per-ayah player.
- **DATABASE_TABLES**: `quran_recitation_editions`, `quran_ayah_audio`, `quran_playback_progress`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Recitation hosts unreachable and their redistribution terms are not documented in an accessible form.
- **NEXT_ACTION**: Reciter or publisher permission, or an external-link record backed by the host's stated terms.
- **Status after this phase**: SOURCE_UNAVAILABLE

### Mosques

- **DOMAIN**: Mosques (`directory-mosques`)
- **CURRENT_SCHEMA**: `directory_listings` (type `mosque`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Overpass and Wikidata unreachable; the GeoAlgeria composite of both (CC0 + ODbL) was found on npm.
- **NEXT_ACTION**: Other regions: run the OSM importer on a connected machine.
- **Status after this phase**: PARTIALLY_READY

### Muslim jobs

- **DOMAIN**: Muslim jobs (`directory-jobs`)
- **CURRENT_SCHEMA**: `directory_listings` (type `job`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Job APIs unreachable and need keys and terms acceptance.
- **NEXT_ACTION**: Owner credentials or employer submissions.
- **Status after this phase**: SOURCE_UNAVAILABLE

### Muslim businesses

- **DOMAIN**: Muslim businesses (`directory-businesses`)
- **CURRENT_SCHEMA**: `directory_listings` (type `business`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No open dataset identifies Muslim-owned businesses.
- **NEXT_ACTION**: Owner or business submissions.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Charities

- **DOMAIN**: Charities (`directory-charities`)
- **CURRENT_SCHEMA**: `directory_listings` (type `charity`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: National registers unreachable; a register does not say whether a charity is Muslim.
- **NEXT_ACTION**: Import a register where reachable, with an explicit faith field.
- **Status after this phase**: SOURCE_UNAVAILABLE

### Muslim professionals

- **DOMAIN**: Muslim professionals (`directory-professionals`)
- **CURRENT_SCHEMA**: `directory_listings` (type `professional`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Self-registration plus moderation is the legitimate route.
- **NEXT_ACTION**: Professionals submit; moderators verify.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Muslim health services

- **DOMAIN**: Muslim health services (`directory-health`)
- **CURRENT_SCHEMA**: `directory_listings` (type `health`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No source; no medical claims are accepted.
- **NEXT_ACTION**: Owner or provider submissions.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Islamic events

- **DOMAIN**: Islamic events (`directory-events`)
- **CURRENT_SCHEMA**: `directory_listings` (type `event`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Organiser-supplied only; Hijri calendar libraries carry no cited authority.
- **NEXT_ACTION**: Organiser feeds or submissions.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Islamic organisations and institutions

- **DOMAIN**: Islamic organisations and institutions (`directory-organisations`)
- **CURRENT_SCHEMA**: `directory_listings` (type `organisation`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: Wikidata and OSM unreachable.
- **NEXT_ACTION**: Owner dataset or submissions.
- **Status after this phase**: OWNER_DATA_REQUIRED

### Volunteering

- **DOMAIN**: Volunteering (`directory-volunteering`)
- **CURRENT_SCHEMA**: `directory_listings` (type `volunteering`): name, arabic_name, description, category, tags, address, city, region, country, lat/lon, phone, email, website, starts_at/ends_at, source, licence, provenance, status, verification_status, duplicate_of. No employer/salary/apply-URL/hours/facilities, no expiry, and the input contract did not carry starts_at/ends_at.
- **IMPORTER**: `scripts/import_directory.py`; `scripts/import_osm_mosques.py` (OpenStreetMap/Overpass, never run live). Partial imports were allowed.
- **ADMIN_WORKFLOW**: Dataset workflow as above, plus the directory moderation queue (approve, reject, hide, verify, suspend), user reports, duplicate scan.
- **API**: `GET /directory/listings` (filters, distance), `/directory/summary`, `/directory/listings/{id}`; suggest, report and moderate endpoints.
- **FRONTEND**: `/[locale]/directory`, `/[locale]/directory/{id}` (search, filters, near me, suggest a listing, report, empty state).
- **DATABASE_TABLES**: `data_sets`, `data_set_imports`, `directory_listings`, `directory_reports`, `platform_audit_events`.
- **CURRENT_DATA_COUNT**: 0 records
- **CURRENT_SOURCE**: none acquired (manifest: "No source acquired")
- **BLOCKER**: No source.
- **NEXT_ACTION**: Organisations submit opportunities.
- **Status after this phase**: OWNER_DATA_REQUIRED

## Gaps found in the existing architecture (closed in this phase)

1. `knowledge_records` had no source-level provenance (work, edition, volume, page, chapter, language, publication/licence/provenance status) and no per-type structure (madhhab, question, ruling, evidence; school and statement; per-grader grades; reliability category). Migration `0086`.
2. Directory listings had no job, volunteering or event fields and no expiry, and the input contract did not accept start/end times. Migration `0086`; expired jobs and finished events are filtered on every read.
3. Imports could be partial: a file with invalid rows still imported the valid ones. Now all-or-nothing by default.
4. The admin workflow had no preview, no unpublish and no per-dataset provenance/history view.
5. Validation lacked checks for invalid URLs, coordinates and dates, unresolved Qur'an/hadith references, orphan relationships and duplicate scholars/books/organisations/mosque locations.
6. The recitation audio schema required a checksum for every file and had no licence, authorisation, external-link, caching or offline fields.
7. Knowledge records were not available to the assistant.
8. Domain-level readiness (READY / PARTIALLY_READY / NEEDS_LICENSE / NEEDS_PROVENANCE / SOURCE_UNAVAILABLE / OWNER_DATA_REQUIRED / NOT_IMPLEMENTED) did not exist; only per-source readiness did.
