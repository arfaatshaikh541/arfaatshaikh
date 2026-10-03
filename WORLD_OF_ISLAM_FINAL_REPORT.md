# World of Islam: final report

Date: 2026-10-03. Branch `claude/world-of-islam-webapp-9rfzue`. Machine-readable twins: [`DATA_READINESS_FINAL.json`](DATA_READINESS_FINAL.json), [`SOURCE_VERIFICATION_FINAL.json`](SOURCE_VERIFICATION_FINAL.json), [`DATA_COVERAGE_FINAL.json`](DATA_COVERAGE_FINAL.json).

## 1. Executive status

**NOT_PRODUCTION_READY.** The platform is honest and well-tested, but it is not data-complete and the full production stack was not verified.

- **No domain is READY.** The Qur'an, the only READY domain in the previous report, was **downgraded to RIGHTS_UNVERIFIED** on evidence found in this pass (section 6). Its text remains published, with its licence and source shown.
- **Hadith text (15,110 narrations) was hidden** (KEEP_HIDDEN, nothing deleted): the packages declare AGPL-3.0 / CC BY 4.0 but name no edition, editor, publisher or upstream source. Hadith gradings (21,185) and tafsir (182,320) stay hidden.
- **Every source host except PyPI, npm and raw.githubusercontent.com is refused by this environment's network policy** (403 on CONNECT; the proxy tells us not to route around it). Wikidata, OpenStreetMap/Overpass, Open Library, Internet Archive, Gutenberg, charity registers, job APIs, recitation hosts and sunnah.com therefore stay SOURCE_BLOCKED. Nothing was imported from a source that was not reached and read.
- **The real `docker-compose.prod.yml` was run, but not completely**: MinIO's registry (quay.io) answers 403. Everything else ran and passed 59 + 45 real-browser checks (section 10).
- Nothing in this report is human-reviewed: no scholar, native Arabic reader or lawyer has seen any of it.

## 2. Domain-by-domain status, counts, coverage and rights

| Domain | Status | Records | Published | Hidden | Rights decision (ledger) | Coverage |
|---|---|---:|---:|---:|---|---|
| Qur'an | **RIGHTS_UNVERIFIED** | 6,236 | 6,236 | 0 | PUBLISH_WITH_CAVEAT | GLOBAL |
| Hadith | **RIGHTS_UNVERIFIED** | 15,110 | 0 | 15,110 | KEEP_HIDDEN | HIDDEN_PENDING_RIGHTS |
| Hadith gradings | **RIGHTS_UNVERIFIED** | 21,185 | 0 | 21,185 | KEEP_HIDDEN | HIDDEN_PENDING_RIGHTS |
| Tafsir | **RIGHTS_UNVERIFIED** | 182,320 | 0 | 182,320 | KEEP_HIDDEN | HIDDEN_PENDING_RIGHTS |
| Fiqh | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Aqeedah | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Seerah | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Scholar biographies | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Islamic terminology | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Islamic history | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Islamic civilization | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Libraries, books and catalogues | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Mosques | **PUBLISHED** | 19,781 | 19,776 | 5 | PUBLISH_WITH_CAVEAT | ALGERIA_ONLY |
| Organisations | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Events | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Charities | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Volunteering | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Businesses | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Professionals | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Health services | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Jobs | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Recitation audio | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |

Rights decisions: `PUBLISH` (redistribution established; none yet), `PUBLISH_WITH_CAVEAT` (shown, open questions stated, never enough for READY), `KEEP_HIDDEN` (kept, not shown). Counts are live database counts from the development database; the verification stack held a filtered copy (section 10).

## 3. Exact sources, licences and rights evidence

Read from the sources themselves on 2026-10-03 (full quotes and URLs in [`data/rights-ledger.json`](data/rights-ledger.json)):

| Dataset | What the source says | Decision |
|---|---|---|
| Hadith Bukhari / Muslim (Arabic) | PyPI metadata and README: AGPL-3.0; acknowledgments say only "Source - Sahih al-Bukhari" and "Translations - By reputable Islamic scholars". No edition, editor or publisher named. | KEEP_HIDDEN |
| Hadith Nawawi-40 (Arabic) | npm: CC-BY-4.0 by an individual author; "sanitized data"; repository is a speed-reader app. | KEEP_HIDDEN |
| Hadith English (Bukhari, Muslim, Nawawi) | Translator not named in the packages (the database records a traditional attribution). | KEEP_HIDDEN |
| Hadith gradings | Upstream `References.md`: grades compiled from scans of printed editions on al-maktaba.org (and one archive.org item). The repository's Unlicense covers its own files, not the graders' gradings. 67,716 grades by 9 graders; 12 of 16 grader/collection pairs map to a named printed work (the four for Zubair Ali Zai point only to his website), none to an edition or page. | KEEP_HIDDEN ([`data/rights-ledger-hadith-gradings.json`](data/rights-ledger-hadith-gradings.json)) |
| Tafsir | 123 editions listed; each names author, language and the site it came from (qul.tarteel.ai 108, quran.com 7, altafsir.com 7, github 1). None states a licence, publisher, editor, translator or year. The repository's MIT licence covers "the Software". | KEEP_HIDDEN ([`data/rights-ledger-tafsir.json`](data/rights-ledger-tafsir.json)) |
| Qur'an Arabic text | PyPI + bundled LICENSE: CC-BY-4.0 (quran-ws). The package's own data file says no source URL is recorded for the main text package and it "cannot be checked against the publisher"; the bundled KFGQPC typeface carries KFGQPC's own licence (free use/copy/distribution, KFGQPC retains title), not CC BY. The application does not ship the typeface. | PUBLISH_WITH_CAVEAT |
| Qur'an translations (Pickthall 1930, Yusuf Ali 1934 ed.) | Public domain by term reasoning (translator death dates). Term and edition rules differ by country; no legal review. | PUBLISH_WITH_CAVEAT |
| Mosques (Algeria) | `@geoalgeria/mosquees` 2.0.4: ODbL 1.0 (OpenStreetMap) and CC0 (Wikidata) data, MIT code. Share-alike effect on this platform undecided; records are community data, individually unverified. | PUBLISH_WITH_CAVEAT |
| OpenITI | RELEASE README read: states no licence; Zenodo/KITAB unreachable. | Stays PROVENANCE_UNCLEAR |
| Rejected earlier (sunan-* packages, @al-mabsut/muslimah, Qivam, calendar libraries) | Unchanged: provenance or licence not established. | Stay rejected |

An npm re-scan (23 search terms, 156 packages) found no source-backed dataset for the empty domains: calculators, API clients, MCP servers over third-party sites (turath.io), UI kits and fonts.

## 4. Source probes (phase 2)

[`scripts/probe_sources.py`](apps/api/scripts/probe_sources.py) probes 58 targets (DNS, TLS/HTTP status, licence page, terms page, data URL, robots.txt) and writes [`data/source-probes.json`](data/source-probes.json). Results from this environment: 2 hosts accessible (PyPI, npm registry); data reachable on 5 (PyPI JSON, npm, raw.githubusercontent.com, api.github.com, the hadith-api files). The other 52 return `Tunnel connection failed: 403 Forbidden` (the proxy records `connect_rejected`: policy denial). `WebFetch` is blocked on the same hosts. **Run the script on the machine the application will run on**: these results describe this sandbox only, and a reachable host would still need its licence and terms read before any import.

To lift the block: change the environment's network access to Custom and add the hosts (Wikidata, Overpass, Open Library, Internet Archive, Gutenberg, quay.io, the charity registers, the recitation hosts, ollama registry). The probe tool then shows what is genuinely reachable.

## 5. What was built in this pass

| Area | Result |
|---|---|
| Rights ledger | `data/rights-ledger.json` + two companion ledgers generated from the upstream catalogues (`scripts/build_rights_ledgers.py`); validated against the manifest; READY now needs an unqualified `PUBLISH` for every published dataset (tests). |
| Hidden hadith | Three Arabic hadith datasets hidden through the manifest and publication policy; 0 of 15,110 published; data kept. |
| Review queues | Generic `review_items` table (migration 0088), admin tab "Human review": 168 Arabic strings grouped GENERAL_UI, QURAN, HADITH, FIQH, AQEEDAH, TAFSIR, SCHOLARSHIP, DIRECTORY (all `NEEDS_NATIVE_REVIEW`; approving requires the reviewer's native-reader attestation) and the mosque queues: **8 name anomalies, 282 co-located different names, 38 near-identical names** (nothing renamed, merged or deleted). |
| Coverage | `GET /api/v1/knowledge/coverage`; the status page shows e.g. "One country only: Algeria". |
| Trust fields | Cited evidence now carries record id, source title, author, edition, publisher, source URL, licence, rights status, retrieval date; the assistant UI shows them. |
| Recitation rights | Owner, territory, streaming/download/redistribution/commercial flags (all default "not granted"); delivery classes `STREAMED_EXTERNALLY`, `HOSTED_WITH_PERMISSION`, `OFFLINE_WITH_PERMISSION`, else `NOT_PLAYABLE`; publishing refuses until rights are recorded. |
| Evidence rules for directories | A Muslim affiliation needs a stated basis and evidence (a name is not evidence); legal registration stays separate; a halal claim needs its certifier; a professional/health specialty needs its evidence; events need an organiser and a page a moderator can check; health/business/charity/job listings carry a notice (no endorsement). |
| Seerah | `unknown` added to the reliability scale; nothing defaulted upward. |
| SSRF | Importer fetches restricted to an HTTPS host allowlist, redirects re-checked (9 tests). |
| Defects fixed | Test-suite rate-limit isolation and event-loop shutdown (first baseline run had 7 failures with a live Redis); duplicated security headers from nginx on API routes; unused import. |

## 6. Why the Qur'an is no longer READY

READY needs gate 3, "rights established". The evidence found today: the package's CC BY 4.0 is the packager's declaration; its own data file states the main text package has no recorded source URL and cannot be checked against KFGQPC; KFGQPC's licence on the bundled typeface is its own. That is a declaration, not an established grant. The text stays published (every ayah is shown with licence and source). To restore READY: written confirmation from KFGQPC, or re-obtain the official package and compare it byte for byte, then record it in the ledger.

**This is a judgement call you may want to review** (as is hiding the hadith text): both follow your rule that a packager's declaration, or an old original work, does not establish rights in a digital edition. To reverse either, record your evidence in `data/rights-ledger.json` and republish from "Data & trust".

## 7. Phases that could not be completed, and why

| Phase | State |
|---|---|
| 3 Scholars, 4 Libraries, 7 Seerah (sources), 8 Terminology, 9 History/civilization, 15 Organisations/charities, 18 Jobs, 13 Recitation (providers) | Blocked by the network policy, or no legitimate source found. Architecture and validation exist; no data was imported. |
| 5 Fiqh, 6 Aqeedah | Structures exist (madhhab/school, topic, question, ruling, evidence, work, edition, volume, page; separate records per position). No source of established rights was reachable; the one candidate stays rejected. |
| 10 Hadith grading | Per-grader ledger built; every grade stays hidden. The structure stores each grader independently with work, edition, page and rights per grade; no winner is ever chosen. |
| 16 Events | Any signed-in user can submit an event (organiser, start/end, location, source page, expiry) and it goes to moderation. **A dedicated organiser role/account type was not built.** |
| 17 Businesses/professionals/health | Rules built (above); no data. |
| 21 AI | Ollama is the provider; with no model installed the API reports `unavailable` and returns quoted, cited evidence only. No model could be pulled (outbound TLS is intercepted here). |
| 22 Arabic QA | Review interface built; **0 of 168 strings approved**. |

## 8. Tests and baseline

Baseline before any change (2026-10-03): web 43 passed, `tsc` and ESLint clean, `next build` OK, migrations up/down/up OK, data validation 14/14, API 724 tests but **7 failed with a live Redis** (rate-limit keys shared across tests) and one more failed on event-loop shutdown; both were test-isolation defects, fixed.

Final: **API 757 passed (incl. 20 integration)**, web 43 passed, `tsc` and ESLint clean, migration cycle through `20261003_0088`, `validate_data.py` 14/14 on the working database. Lint: the repository's configured ruff rules (`E,F,I,B,UP,S`, line length 100) fail on thousands of pre-existing style findings; `ruff --select F,B` is clean on every new module.

## 9. Production build and migrations

All four images (api, web, migrate, worker) were built from the real Dockerfiles; `next build` succeeds with `WOI_BASE_PATH=/worldofislam`; the stack's `migrate` service ran `alembic upgrade head` and exited 0.

## 10. Production verification (real `docker-compose.prod.yml`)

Run on this VM at `https://app.arfaat.com/worldofislam` through a local hosts mapping and a self-signed certificate. **Not** the real production host. Record: [`data/verification-prod-compose.json`](data/verification-prod-compose.json).

| Service | Result |
|---|---|
| postgres, redis, nginx | healthy (Docker Hub images, unmodified) |
| migrate, api, web | built from the real Dockerfiles; healthy |
| ollama | healthy (exact `ollama/ollama:latest`); no model installed |
| worker | Celery connected and ready; **registers no tasks** |
| backup | wrote a dump (448 bytes: of an empty database); restore not exercised |
| **minio, minio-init** | **NOT RUN: quay.io returns 403.** `/health/ready` correctly reports `object_storage: false` (degraded). |

Deviations (all disclosed in the JSON): MinIO disabled and the API's dependency on it removed; builds used Dockerfile copies that add the sandbox's TLS-intercepting CA to the builder stage only; a filtered copy of the data (hidden tafsir and 482 hidden translation editions left out for disk space); self-signed certificate.

Browser suites (real Chromium): `browser-verify.cjs` 59 passed / 0 failed: dashboard honesty, hidden records not exposed, English and Arabic RTL, mobile (no horizontal scroll), the admin click-through (upload, preview errors, import, verify, publish, unpublish, provenance, rollback, audit log), expired jobs/events excluded, review queues, assistant citation and abstention. `prod-extra-verify.cjs` 45 passed / 0 failed: security headers, 404 handling, PWA and service worker, command palette, search, authentication, authorisation, injection probes, rate limiting, offline matrix. Console/network noise is classified in the JSON (expected 401s on anonymous probes, aborted prefetches, the importer's clean 502 because the container cannot reach npm from this sandbox).

## 11. Security verification (automated only)

pip-audit (162 locked packages) and pnpm audit: no known vulnerabilities. Secret scan: placeholders and test fixtures only. CORS: an unlisted origin gets no allow-origin. API docs/OpenAPI are not exposed. Only nginx publishes ports (80, 443). Admin APIs: anonymous 401, non-admin 403. CSRF enforced. Rate limit 429. Malformed uploads 422, oversized 413. SQL-injection style input and markup in a display name and in a query string produced no error and no execution. Importer SSRF allowlist added. **Not done:** external penetration test, DoS testing, review of the real host.

## 12. AI verification

Provider order is local Ollama first; no paid API is required. In the stack the API returns `ai_synthesis.status = unavailable` (no model installed) and a quoted, cited answer; with no sufficient source it abstains. Every cited item carries an authority class and the trust fields. A synthesis would be shown only if every sentence passes citation validation (tested with a stub model).

## 13. Offline verification

| Capability | Result |
|---|---|
| OFFLINE_UI | Works for pages visited while online (layout only). |
| OFFLINE_CACHED_DATA | Not available, by design: API responses are never cached. |
| OFFLINE_SEARCH | Works for Arabic search over an explicitly downloaded Qur'an. |
| OFFLINE_QURAN | Works for surahs downloaded explicitly and opened once online. |
| OFFLINE_AUDIO | Not available: no recitation is published. |
| OFFLINE_AI | Not available: no model installed. |

## 14. Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| production build succeeds | **PASS** | next build exit 0; api, web, migrate and worker images built from the real Dockerfiles (CA injected into builder stages only) |
| migrations succeed | **PASS** | alembic up/down/up to 20261003_0088 on a scratch database; the stack's migrate service completed |
| all tests pass | **PASS** | API 757 passed (incl. 20 integration); web 43 passed; typecheck and ESLint clean |
| security checks pass | **PASS_AUTOMATED_ONLY** | pip-audit and pnpm audit clean; secret scan found placeholders only; CORS, CSRF, authn/authz, injection, upload, SSRF and rate-limit checks passed. No external penetration test. |
| real production compose is tested | **FAIL** | docker-compose.prod.yml was run, but MinIO and its init job could not be started (quay.io answers 403), so the complete file was not run |
| required services are tested | **FAIL** | MinIO not run; Ollama has no model (pull failed); the worker registers no tasks; the backup job was exercised only against an empty database |
| frontend works under /worldofislam | **PASS** | 59 + 45 browser checks passed on the stack (local hosts mapping and self-signed certificate, not app.arfaat.com) |
| AI works or clearly reports unavailable | **PASS** | no model is installed; the API reports ai_synthesis.status = unavailable and still returns cited, quoted evidence |
| every published dataset has provenance | **PASS** | scripts/validate_data.py 14/14 on the working database |
| every published dataset has appropriate rights status | **FAIL** | 5 published datasets rest on PUBLISH_WITH_CAVEAT, not on established rights: quran-arabic-uthmani-hafs, quran-tajweed-quranws, quran-translation-pickthall, quran-translation-yusufali-1934, directory-mosques |
| geographic coverage is explicit | **PASS** | GET /knowledge/coverage and the status page state the countries; mosques are ALGERIA_ONLY |
| religious claims are source-backed | **PASS** | every cited passage carries source, licence and authority class; with no source the assistant abstains |
| hadith grades are attributed | **NOT_APPLICABLE** | no hadith grade is published; the structure stores each grader separately and never picks a winner |
| scholarly disagreement is preserved | **PASS_STRUCTURE_ONLY** | fiqh/aqeedah records are per madhhab/school and listed separately (tested); no such records exist yet |
| no fabricated records exist | **NOT_VERIFIED** | every imported record comes from a named source with a checksum; absence of fabrication is not independently proven and no human reviewed the data |
| no fake directories exist | **PASS** | the only listings are 19,781 imported mosque records (Algeria); test fixtures are rolled back |
| no fake audio exists | **PASS** | no recitation is published; delivery classes require recorded rights |
| no fake citations exist | **PASS** | citation validation rejects references that are not in the retrieved evidence (tests) |
| domains READY | **FAIL** | status counts: {'RIGHTS_UNVERIFIED': 4, 'EMPTY': 12, 'SOURCE_BLOCKED': 5, 'PUBLISHED': 1}; no domain is READY |

## 15. Known limitations

- Rights reasoning is mine from the cited sources; no lawyer reviewed it. Public-domain status of translations is jurisdiction-dependent.
- The Qur'an Arabic text has never been compared by a person with a printed mushaf.
- `nginx` resolves `api` and `web` at start; after recreating those containers, restart nginx (not shown to be necessary here).
- Arabic strings, including those added in this pass, are unreviewed.
- The mosque data is Algeria only, community data, not individually verified; ODbL share-alike is undecided.
- The verification stack used a hosts mapping and a self-signed certificate; service-worker registration needed `--ignore-certificate-errors`.

## 16. Remaining blockers and exact next actions

1. **Network access**: add the source hosts (and quay.io) to the environment's allowed domains, or run `scripts/probe_sources.py` on the production host. Then read each source's licence and terms and record them in the ledger before any import.
2. **MinIO**: obtain `quay.io/minio/minio:RELEASE.2025-07-23T15-54-02Z` and `quay.io/minio/mc:RELEASE.2025-07-21T05-28-08Z`, run the unmodified `docker-compose.prod.yml` on the real host, then re-run `infrastructure/verify/browser-verify.cjs` and `prod-extra-verify.cjs` against `https://app.arfaat.com/worldofislam`.
3. **Rights decisions** (yours): confirm or reverse the Qur'an downgrade and the hadith hiding; obtain KFGQPC's written confirmation; identify the Arabic hadith editions; obtain grader/publisher permission for gradings; per-edition rights for tafsir.
4. **Humans**: a native Arabic reader (168 strings), a qualified scholar for any religious content added, a lawyer for the rights questions.
5. **Model**: `docker compose exec ollama ollama pull <model>` on a host with access to the Ollama registry.
6. **Worker**: add its tasks (it registers none) and test the backup restore against real data.
7. **Organiser accounts**: add an organiser role if you want events to be submitted as a separate account type.
8. **Unreviewed items**: work the 8 / 282 / 38 mosque queues in "Human review".
