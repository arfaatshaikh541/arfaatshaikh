# World of Islam: data completion report

Date: 2026-10-01. Branch `claude/world-of-islam-webapp-9rfzue`.

**The project is not data-complete.** Two real datasets were acquired, verified as far as the available evidence allows, and
imported; one is published (with a partial scope) and one is staged because the right to publish it is not established. Every
other pending domain has a ready importer, validator, admin workflow, API and honest empty state, and is waiting for a source
that could be verified or for owner-supplied data. No religious text, grade, scholar biography, ruling or listing was written
from memory, and no source was used whose licence or provenance could not be read.

## Result by domain

| Domain | Records | Status |
|---|---|---|
| Fiqh, Aqeedah, Seerah, Islamic terminology, Islamic history, Islamic civilization | 0 | OWNER_DATA_REQUIRED |
| Hadith grading | 21,185 (67,681 per-grader grades), staged | NEEDS_LICENSE |
| Islamic library, Scholar biographies | 0 | SOURCE_UNAVAILABLE |
| Qur'an recitation audio | 0 | SOURCE_UNAVAILABLE |
| Mosques | 19,781 (19,776 visible), Algeria only | PARTIALLY_READY |
| Muslim jobs, Charities | 0 | SOURCE_UNAVAILABLE |
| Muslim businesses, professionals, health services, Islamic events, organisations, Volunteering | 0 | OWNER_DATA_REQUIRED |

Full table with source, licence, provenance, importer, validation, admin, frontend and remaining action: [`docs/DATA_READINESS.md`](docs/DATA_READINESS.md).
No domain is READY.

## The eleven items you asked for

1. **Domains fully populated:** none.
2. **Partially populated:** Mosques (Algeria only: 20,759 source records, 19,781 imported, 19,776 shown). Every listing is displayed as "Not verified".
3. **Blocked by licensing:** Hadith grading (imported and hidden). Already held from earlier work and still hidden: English hadith translations, 482 further Qur'an translations, 54 tafsir editions.
4. **Blocked by provenance:** the `sunan-abi-dawud` / `sunan-al-nasai` / `sunan-ibn-majah` / `sunnah` npm packages (AGPL declared by the packager, no upstream source or translator named), OpenITI (no licence retrievable), `@al-mabsut/muslimah` (fiqh guidance with no cited work or page and no content licence), the Hijri-calendar libraries' event lists. None was imported.
5. **Blocked by source availability** (the hosts did not answer from the build environment on 2026-10-01): OpenStreetMap Overpass, Wikidata, Open Library / Internet Archive / Gutenberg, national charity registers, job APIs, sunnah.com API, and the recitation audio hosts (everyayah.com, mp3quran.net, api.quran.com, cdn.islamic.network). Their licences were not assessed, and nothing is held against them.
6. **Requiring owner data:** fiqh, aqeedah, seerah, terminology, history, civilization, businesses, professionals, health services, events, organisations, volunteering (and jobs/charities/library/scholars/audio unless the hosts can be reached from your server).
7. **Exact sources used:**
   - `@geoalgeria/mosquees` 2.0.4 from npm (tarball sha256 `5705920a697b8fd75b4f5d2ee18a99a276f9c7cc4d21fe4024a7745c87dadfb5`; the registry's sha512 integrity value is checked on every download).
   - `fawazahmed0/hadith-api`, `info.json` at git tag `1` (sha256 `cf1ced267ada8f606f95eb84e2b6ddfa87bfa2a6a9dd4cb2a5d9a8c1734f10fb`).
8. **Exact licences:**
   - Mosques: data under ODbL 1.0 (© OpenStreetMap contributors) for 6,581 records and CC0-1.0 (Wikidata) for 13,200 records; package code MIT. Read from the package `LICENSE`, `dataset-metadata.json` and README. ODbL requires attribution and share-alike for a derived database; every listing and the directory page carry the attribution.
   - Hadith gradings: the repository is under the Unlicense, which covers its author's own work only. `References.md` shows the grades were compiled from al-maktaba.org books and zubairalizai.com, whose terms could not be read. Status LICENSE_REQUIRED, so the dataset is staged and public readers cannot see it.
9. **Exact records imported:**
   - Mosques: 19,781 listings (978 of the 20,759 source records have no name and were skipped, not given one). 5 probable duplicates were linked and hidden. 15,136 have an Arabic name; 15,917 have exact and 3,864 approximate coordinates; 2,880 carry a denomination taken from an OSM tag with that source stated (2,867 sunni, 10 ibadi, 3 sufi); denominations on Wikidata-only records were not kept.
   - Hadith gradings: 21,185 records, 67,681 grader entries. Abu Dawud 5,274, Ibn Majah 4,341, Malik 1,858, al-Nasa'i 5,758, al-Tirmidhi 3,954. 35 placeholder grades ("-") were dropped. In 15,596 records the graders' grade labels are not all identical; each grader is listed separately and nothing is reconciled. Bukhari and Muslim carry no grades in the file and none were added.
10. **Exact tests passed:**
    - API: 668 unit and contract tests plus 14 integration tests against a real PostgreSQL database = **682 passed** (run twice; the integration tests are re-runnable). New: `tests/test_data_completion.py` (24 tests) and two new integration tests (unpublish with the assistant citing sourced records; expired jobs and job-field enforcement) plus an extended lifecycle test (preview, all-or-nothing, provenance view); two source-sync tests added to `tests/test_data_validation.py`.
    - `scripts/validate_data.py`: **13 of 13 rules PASS** on the populated database.
    - Migrations: upgrade, downgrade to base, upgrade again on an empty database gives identical schemas (`MIGRATION CYCLE OK`, 3,488 columns); `0086` also ran on a copy of the populated database.
    - Web: `tsc --noEmit` clean, ESLint clean, 38 unit tests passed (9 files), `next build` succeeded with `WOI_BASE_PATH=/worldofislam`.
    - Browser (Playwright/Chromium against `next dev` with base path `/worldofislam` and the API on the populated database): 8 of 8 page checks passed, covering the mosque directory (English desktop, Arabic RTL mobile, no horizontal scroll, attribution shown, "Not verified" shown), the exact empty-state wording for Fiqh (English and Arabic) and Seerah, the staged hadith-grading state, and the Qur'an reader audio notice.
    - `ruff --select F,B` clean on every new and changed file; `mypy app` reports only four missing-stub notices for `boto3` in files this work did not touch.
11. **Exact remaining blockers:** see below.

## Remaining blockers

- **Hadith grading rights.** Confirm the right to publish the compiled grades (or replace them with a source that allows it), spot-check a sample against the graders' printed works, then use *Data & trust* (or `scripts/dataset_action.py`) to mark verified and publish. The five graded collections are not loaded in the hadith reader, so these records cite collection and number without linking to hadith text.
- **Mosques outside Algeria.** Run `scripts/import_osm_mosques.py` for your regions on a machine that can reach Overpass; it records the same ODbL attribution.
- **Owner datasets** for the OWNER_DATA_REQUIRED domains. The contract tells the supplier exactly what each record needs (named work, edition, page, language, madhhab or school, grader and grade source, reliability category, employer and apply URL and expiry for jobs ...); a file with any invalid row is rejected whole.
- **Recitation audio** needs the reciter's or publisher's permission, or an external-link record backed by the host's stated terms.
- **Hosts unreachable from the build environment** (list above) may be reachable from your server; the importers and the source list in `docs/SOURCE_VERIFICATION.md` are ready for that.

## What was built (extending, not rebuilding)

- Migration `0086`: source-level provenance and per-type structure on knowledge records; job, event, volunteering, expiry and attribute fields on listings; recitation audio delivery mode (hosted or external link), licence, authorisation, caching and offline permissions.
- Contracts: fiqh (one record per madhhab position, ruling, evidence), aqeedah, seerah (reliability category), hadith grading (one entry per grader, never inferred), terminology, library (no copyrighted files), Qur'an and hadith references; per-type listing rules; no donation links; mosque denomination only with its source.
- Imports are all-or-nothing by default, with preview, rollback, unpublish and a provenance/history view in the admin panel; `scripts/dataset_action.py` and `scripts/scan_directory_duplicates.py` for operators.
- Expired jobs and finished events disappear on every read; duplicates are linked, not deleted.
- 13 validation rules (URLs, coordinates, dates, references, orphans, duplicate scholars/books/organisations/mosques, record counts).
- The assistant can cite published knowledge records (`[K1]`...) with work, edition, page, licence and position; positions stay separate; uncertainty is stated; it still abstains without a primary source.
- Empty states use the exact wording required and are shown only while a domain has no published records; a domain with staged data says it is awaiting rights, not that nothing was imported.
- Documents: `docs/PENDING_DATA_AUDIT.md`, `docs/SOURCE_VERIFICATION.md`, `docs/DATA_READINESS.md` (generated, checked by tests), updated `docs/data-contracts.md`, `docs/data-sources.md`, `docs/FEATURE_STATUS.md`.

## Things I did not verify

- The mosque data was not checked against ground truth. It is a community composite: one result near central Algiers is the "Grande synagogue d'Alger" (a building Wikidata classifies as a mosque), so expect other oddities. That is why every listing is labelled not verified and users can report errors.
- The hadith grades were copied faithfully from the file; they were not compared with the printed works.
- The admin panel's new preview, unpublish and history screens compile and their API calls are tested, but I did not click through them in a browser. The browser checks ran against the development server, not the production Docker/nginx stack.
- The Arabic interface strings I added (empty states, attribution, labels) should be read by a native Arabic speaker.
- The first `sync_manifest.py` on the full database takes many minutes (it rewrites publication flags on the large tafsir tables).
