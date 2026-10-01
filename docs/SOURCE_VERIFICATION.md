# Source verification

Generated from `data/source-candidates.json` (candidates examined for the pending domains) and `data/source-manifest.json` (datasets already stored) by `scripts/generate_source_verification.py`. Edit the JSON, not this file.

A source is **VERIFIED** only when its licence text and provenance were read. Nothing becomes verified silently: a candidate changes status only by an edit to `data/source-candidates.json` that is reviewed in version control, and a stored dataset only through the audited `mark_verified` action (with a note) in *Data & trust*.

## Status legend

- **VERIFIED** - Licence text and provenance were read and permit the stated use.
- **NEEDS_MANUAL_REVIEW** - Looked at, but a person must decide (or the owner must supply the data).
- **LICENSE_REQUIRED** - The data is real but the right to publish it is not established.
- **PROVENANCE_UNCLEAR** - The upstream origin or the licence could not be established.
- **TECHNICALLY_UNAVAILABLE** - A legitimate source, but it could not be reached or accessed from the build environment.
- **NOT_ALLOWED_FOR_REDISTRIBUTION** - The terms forbid redistribution.

## Summary

| Status | Candidates examined |
|---|---|
| VERIFIED | 1 |
| NEEDS_MANUAL_REVIEW | 2 |
| LICENSE_REQUIRED | 3 |
| PROVENANCE_UNCLEAR | 4 |
| TECHNICALLY_UNAVAILABLE | 7 |
| NOT_ALLOWED_FOR_REDISTRIBUTION | 1 |

## Candidates examined for the pending domains

Last verified 2026-10-01. Hosts marked TECHNICALLY_UNAVAILABLE returned no response from the build environment on that date; that says nothing against their licences.

### GeoAlgeria @geoalgeria/mosquees 2.0.4 - VERIFIED

`geoalgeria-mosquees` - backs dataset `directory-mosques`

- **SOURCE_NAME**: GeoAlgeria @geoalgeria/mosquees 2.0.4
- **SOURCE_URL**: https://www.npmjs.com/package/@geoalgeria/mosquees
- **OWNER**: Yasser's Studio (compiler); Wikidata and OpenStreetMap contributors (upstream)
- **TYPE**: open dataset (composite)
- **DATA_DOMAIN**: mosque
- **LICENSE**: ODbL 1.0 for OpenStreetMap-derived records; CC0-1.0 for Wikidata records; MIT for package code
- **LICENSE_URL**: https://opendatacommons.org/licenses/odbl/1-0/
- **PROVENANCE**: Package LICENSE and dataset-metadata.json state the terms; README documents the Wikidata SPARQL + OSM Overpass build and the ~150 m merge; every record keeps its Wikidata/OSM reference. Not an official registry.
- **ACCESS_METHOD**: npm tarball, sha512 integrity verified; scripts/build_geoalgeria_mosques.py
- **REDISTRIBUTION_ALLOWED**: Yes, with attribution; share-alike for a derived database (ODbL)
- **COMMERCIAL_USE_ALLOWED**: Yes (ODbL permits commercial use with attribution and share-alike)
- **ATTRIBUTION_REQUIRED**: Yes: © OpenStreetMap contributors; Wikidata CC0 needs none
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: VERIFIED
- **NOTES**: Algeria only. Wilaya/commune are derived by centroid, not from the sources. 978 of 20,759 records have no name and are skipped. Denomination kept only where the package took it from an OSM tag.

### npm @trydaleel/domain-islamic-hadith 0.1.4 - NEEDS_MANUAL_REVIEW

`npm-trydaleel-hadith-domain`

- **SOURCE_NAME**: npm @trydaleel/domain-islamic-hadith 0.1.4
- **SOURCE_URL**: https://www.npmjs.com/package/@trydaleel/domain-islamic-hadith
- **OWNER**: imranatgithub
- **TYPE**: software (grade taxonomy)
- **DATA_DOMAIN**: hadith_grading
- **LICENSE**: Apache-2.0 declared
- **LICENSE_URL**: https://www.npmjs.com/package/@trydaleel/domain-islamic-hadith
- **PROVENANCE**: A code package of grade labels and authorities with no stated source for the authority data.
- **ACCESS_METHOD**: npm tarball (read, not imported)
- **REDISTRIBUTION_ALLOWED**: Yes for the code
- **COMMERCIAL_USE_ALLOWED**: Yes for the code
- **ATTRIBUTION_REQUIRED**: Per Apache-2.0
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: NEEDS_MANUAL_REVIEW
- **NOTES**: Not a dataset of gradings; the authority list has no stated provenance, so it is not used.

### Owner-supplied datasets (scholars, organisations, institutions, employers) - NEEDS_MANUAL_REVIEW

`owner-supplied`

- **SOURCE_NAME**: Owner-supplied datasets (scholars, organisations, institutions, employers)
- **SOURCE_URL**: (owner)
- **OWNER**: The platform owner
- **TYPE**: owner data
- **DATA_DOMAIN**: fiqh, aqeedah, seerah, terminology, history, civilization, scholar, business, charity, professional, organisation, event, volunteering, health
- **LICENSE**: Per dataset: owner must state rights
- **LICENSE_URL**: (owner)
- **PROVENANCE**: Whatever the owner can document.
- **ACCESS_METHOD**: Admin upload (preview, validate, import) or scripts/import_*.py
- **REDISTRIBUTION_ALLOWED**: Per dataset
- **COMMERCIAL_USE_ALLOWED**: Per dataset
- **ATTRIBUTION_REQUIRED**: Per dataset
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: NEEDS_MANUAL_REVIEW
- **NOTES**: The pipeline is ready; each dataset enters as staged until rights are confirmed.

### fawazahmed0/hadith-api: per-grader hadith grades (info.json, tag 1) - LICENSE_REQUIRED

`hadith-api-grades` - backs dataset `hadith-grading`

- **SOURCE_NAME**: fawazahmed0/hadith-api: per-grader hadith grades (info.json, tag 1)
- **SOURCE_URL**: https://github.com/fawazahmed0/hadith-api/tree/1
- **OWNER**: fawazahmed0 (aggregator); the graders and al-maktaba.org / zubairalizai.com (compiled sources)
- **TYPE**: aggregated dataset
- **DATA_DOMAIN**: hadith_grading
- **LICENSE**: Unlicense (repository); rights in the compiled grades not established
- **LICENSE_URL**: https://github.com/fawazahmed0/hadith-api/blob/1/LICENSE
- **PROVENANCE**: References.md names the al-maktaba.org book (or site) each grader's grades were taken from. Not independently checked against the printed works.
- **ACCESS_METHOD**: raw.githubusercontent.com; scripts/build_hadith_grading_records.py
- **REDISTRIBUTION_ALLOWED**: Unknown: the Unlicense covers only the repository author's own work
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Recommended
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: LICENSE_REQUIRED
- **NOTES**: Imported and STAGED (21,185 records, 67,681 grader entries); hidden from every public view until rights are confirmed in Data & trust. Five collections not loaded in the reader, so no link to hadith text.

### fawazahmed0/hadith-api: English/other hadith translations - LICENSE_REQUIRED

`hadith-api-translations` - backs dataset `hadith-bukhari-english`

- **SOURCE_NAME**: fawazahmed0/hadith-api: English/other hadith translations
- **SOURCE_URL**: https://github.com/fawazahmed0/hadith-api/tree/1
- **OWNER**: fawazahmed0 (aggregator); translators listed as 'Unknown'
- **TYPE**: aggregated dataset
- **DATA_DOMAIN**: hadith translations
- **LICENSE**: Unlicense (repository); translators' rights not established
- **LICENSE_URL**: https://github.com/fawazahmed0/hadith-api/blob/1/LICENSE
- **PROVENANCE**: Edition metadata gives author 'Unknown' and no source.
- **ACCESS_METHOD**: raw.githubusercontent.com
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Recommended
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: LICENSE_REQUIRED
- **NOTES**: Already held, staged and hidden (hadith-bukhari-english, hadith-muslim-english).

### npm quran-recitors / quran-mp3 (wrappers of mp3quran.net) - LICENSE_REQUIRED

`npm-mp3quran-wrappers` - backs dataset `audio-quran-recitations`

- **SOURCE_NAME**: npm quran-recitors / quran-mp3 (wrappers of mp3quran.net)
- **SOURCE_URL**: https://www.npmjs.com/package/quran-recitors
- **OWNER**: ismnoiet
- **TYPE**: API wrapper
- **DATA_DOMAIN**: recitation audio
- **LICENSE**: MIT declared for the wrapper code only
- **LICENSE_URL**: https://www.npmjs.com/package/quran-recitors
- **PROVENANCE**: Reads a third-party site; the MIT licence says nothing about mp3quran.net's recordings.
- **ACCESS_METHOD**: npm metadata (read)
- **REDISTRIBUTION_ALLOWED**: Unknown for recordings
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: LICENSE_REQUIRED
- **NOTES**: Not used.

### npm @al-mabsut/muslimah 0.2.3 - PROVENANCE_UNCLEAR

`npm-al-mabsut-muslimah`

- **SOURCE_NAME**: npm @al-mabsut/muslimah 0.2.3
- **SOURCE_URL**: https://github.com/al-mabsut/muslimah
- **OWNER**: Mufti Khalil Johnson
- **TYPE**: fiqh guidance for an application
- **DATA_DOMAIN**: fiqh
- **LICENSE**: ISC declared in package.json; no licence file for the content
- **LICENSE_URL**: https://www.npmjs.com/package/@al-mabsut/muslimah
- **PROVENANCE**: Hanafi guidance on women's matters; content pages cite no work, edition, volume or page.
- **ACCESS_METHOD**: npm tarball and raw.githubusercontent.com (read, not imported)
- **REDISTRIBUTION_ALLOWED**: Unknown for the content
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **NOTES**: Not imported: fiqh records must be traceable to a named work and page (data contract).

### npm islamic-utils / islamic-date (event lists) - PROVENANCE_UNCLEAR

`npm-islamic-calendar-events`

- **SOURCE_NAME**: npm islamic-utils / islamic-date (event lists)
- **SOURCE_URL**: https://www.npmjs.com/package/islamic-utils
- **OWNER**: various packagers
- **TYPE**: software
- **DATA_DOMAIN**: directory events (occasions)
- **LICENSE**: MIT declared (code)
- **LICENSE_URL**: https://www.npmjs.com/package/islamic-utils
- **PROVENANCE**: Occasion lists are embedded in code with no cited authority.
- **ACCESS_METHOD**: npm metadata (read)
- **REDISTRIBUTION_ALLOWED**: Unknown for the data
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **NOTES**: Not imported. Community events come from organisers, not a calendar library.

### npm sunan-abi-dawud, sunan-al-nasai, sunan-ibn-majah, sunnah (SENODROOM) - PROVENANCE_UNCLEAR

`npm-sunan-packages`

- **SOURCE_NAME**: npm sunan-abi-dawud, sunan-al-nasai, sunan-ibn-majah, sunnah (SENODROOM)
- **SOURCE_URL**: https://www.npmjs.com/package/sunan-abi-dawud
- **OWNER**: muhammadsaadamin (packager)
- **TYPE**: packaged dataset
- **DATA_DOMAIN**: hadith
- **LICENSE**: AGPL-3.0 declared by the packager
- **LICENSE_URL**: https://github.com/SENODROOM/sunan-abi-dawud
- **PROVENANCE**: README and data file state no upstream source or translator; an AGPL declaration cannot grant rights the packager does not hold in the English text.
- **ACCESS_METHOD**: npm tarball (read, not imported)
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **NOTES**: Not imported. The Arabic text of these classical works would be public domain, but the edition and the English translation are unattributed.

### OpenITI corpus and metadata (RELEASE repository) - PROVENANCE_UNCLEAR

`openiti`

- **SOURCE_NAME**: OpenITI corpus and metadata (RELEASE repository)
- **SOURCE_URL**: https://github.com/OpenITI/RELEASE
- **OWNER**: OpenITI project
- **TYPE**: scholarly corpus
- **DATA_DOMAIN**: library_work, scholar, history, civilization
- **LICENSE**: Not established
- **LICENSE_URL**: https://github.com/OpenITI/RELEASE
- **PROVENANCE**: The repository README states no licence; LICENSE and metadata files returned 404 from the build environment.
- **ACCESS_METHOD**: raw.githubusercontent.com (README only)
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **NOTES**: Not used. A catalogue of authors, works and death dates would fill several domains; it needs its licence confirmed first.

### Job APIs/feeds (e.g. Adzuna, USAJobs, employer feeds) - TECHNICALLY_UNAVAILABLE

`job-feeds` - backs dataset `directory-jobs`

- **SOURCE_NAME**: Job APIs/feeds (e.g. Adzuna, USAJobs, employer feeds)
- **SOURCE_URL**: https://api.adzuna.com
- **OWNER**: Feed operators / employers
- **TYPE**: authorised API
- **DATA_DOMAIN**: job
- **LICENSE**: Per-provider API terms (keys required)
- **LICENSE_URL**: https://api.adzuna.com
- **PROVENANCE**: Requires a key and terms acceptance by the platform owner.
- **ACCESS_METHOD**: HTTP (unreachable, 2026-10-01)
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **NOTES**: Needs owner credentials or employer submissions. Job listings require employer, application URL and expiry; none are invented.

### National charity registers (e.g. Charity Commission for England and Wales, US IRS exempt-organisation data) - TECHNICALLY_UNAVAILABLE

`official-charity-registers` - backs dataset `directory-charities`

- **SOURCE_NAME**: National charity registers (e.g. Charity Commission for England and Wales, US IRS exempt-organisation data)
- **SOURCE_URL**: https://register-of-charities.charitycommission.gov.uk
- **OWNER**: Government bodies
- **TYPE**: official register
- **DATA_DOMAIN**: charity, organisation
- **LICENSE**: Not verified from this environment
- **LICENSE_URL**: https://register-of-charities.charitycommission.gov.uk
- **PROVENANCE**: Official registration data.
- **ACCESS_METHOD**: HTTP (unreachable, 2026-10-01)
- **REDISTRIBUTION_ALLOWED**: Unknown until read
- **COMMERCIAL_USE_ALLOWED**: Unknown until read
- **ATTRIBUTION_REQUIRED**: Unknown until read
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **NOTES**: Hosts unreachable. Note that a register lists charities, not whether a charity is Muslim: a faith filter would need an explicit field.

### Open Library / Internet Archive / Project Gutenberg / HathiTrust catalogues - TECHNICALLY_UNAVAILABLE

`open-library-catalogues` - backs dataset `library-works`

- **SOURCE_NAME**: Open Library / Internet Archive / Project Gutenberg / HathiTrust catalogues
- **SOURCE_URL**: https://openlibrary.org/data
- **OWNER**: Internet Archive and others
- **TYPE**: bibliographic catalogues
- **DATA_DOMAIN**: library_work
- **LICENSE**: Per-catalogue; not verified from this environment
- **LICENSE_URL**: https://openlibrary.org/developers/licensing
- **PROVENANCE**: Bibliographic metadata.
- **ACCESS_METHOD**: HTTP (unreachable, 2026-10-01)
- **REDISTRIBUTION_ALLOWED**: Unknown until read
- **COMMERCIAL_USE_ALLOWED**: Unknown until read
- **ATTRIBUTION_REQUIRED**: Unknown until read
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **NOTES**: Hosts unreachable. Metadata-only records (no files) are the intended use.

### OpenStreetMap via Overpass API - TECHNICALLY_UNAVAILABLE

`openstreetmap-overpass`

- **SOURCE_NAME**: OpenStreetMap via Overpass API
- **SOURCE_URL**: https://overpass-api.de
- **OWNER**: OpenStreetMap contributors
- **TYPE**: open map data
- **DATA_DOMAIN**: mosque, organisation, charity, health, business
- **LICENSE**: ODbL 1.0
- **LICENSE_URL**: https://www.openstreetmap.org/copyright
- **PROVENANCE**: Crowd-sourced map data.
- **ACCESS_METHOD**: Overpass API; scripts/import_osm_mosques.py (ready)
- **REDISTRIBUTION_ALLOWED**: Yes with attribution; share-alike
- **COMMERCIAL_USE_ALLOWED**: Yes
- **ATTRIBUTION_REQUIRED**: Yes: © OpenStreetMap contributors
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **NOTES**: Host unreachable from the build environment (HTTP 000, 2026-10-01). Run the importer on the production server for the regions you serve.

### Recitation audio hosts: everyayah.com, mp3quran.net, api.quran.com, cdn.islamic.network - TECHNICALLY_UNAVAILABLE

`quran-recitation-sources` - backs dataset `audio-quran-recitations`

- **SOURCE_NAME**: Recitation audio hosts: everyayah.com, mp3quran.net, api.quran.com, cdn.islamic.network
- **SOURCE_URL**: https://everyayah.com
- **OWNER**: Reciters / publishers / site operators
- **TYPE**: audio hosting
- **DATA_DOMAIN**: recitation audio
- **LICENSE**: Redistribution rights not established for any of them
- **LICENSE_URL**: https://everyayah.com
- **PROVENANCE**: Reciter and publisher permission not documented in an accessible form.
- **ACCESS_METHOD**: HTTP (all unreachable, 2026-10-01)
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **NOTES**: No audio is copied. Link-only records need the host's stated permission; the schema (QuranRecitationEdition, QuranAyahAudio) and player exist.

### sunnah.com API - TECHNICALLY_UNAVAILABLE

`sunnah-com-api`

- **SOURCE_NAME**: sunnah.com API
- **SOURCE_URL**: https://sunnah.com/developers
- **OWNER**: sunnah.com
- **TYPE**: API
- **DATA_DOMAIN**: hadith, hadith_grading
- **LICENSE**: Terms not reviewed (API key required)
- **LICENSE_URL**: https://sunnah.com/developers
- **PROVENANCE**: Grades are attributed per collection.
- **ACCESS_METHOD**: API key
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **NOTES**: Host unreachable and a key is required; owner would need to apply and accept the terms.

### Wikidata SPARQL - TECHNICALLY_UNAVAILABLE

`wikidata`

- **SOURCE_NAME**: Wikidata SPARQL
- **SOURCE_URL**: https://query.wikidata.org
- **OWNER**: Wikimedia Foundation
- **TYPE**: open knowledge base
- **DATA_DOMAIN**: scholar, library_work, history, civilization, organisation, mosque
- **LICENSE**: CC0-1.0
- **LICENSE_URL**: https://www.wikidata.org/wiki/Wikidata:Licensing
- **PROVENANCE**: Crowd-sourced; each statement can carry references.
- **ACCESS_METHOD**: SPARQL endpoint
- **REDISTRIBUTION_ALLOWED**: Yes
- **COMMERCIAL_USE_ALLOWED**: Yes
- **ATTRIBUTION_REQUIRED**: No
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **NOTES**: Host unreachable from the build environment (2026-10-01). A good source of scholars, works and dates once reachable, with the Wikidata item cited per record.

### Qivam API (mosque directory, prayer times) via @qivam/client - NOT_ALLOWED_FOR_REDISTRIBUTION

`qivam-api`

- **SOURCE_NAME**: Qivam API (mosque directory, prayer times) via @qivam/client
- **SOURCE_URL**: https://qivam.com
- **OWNER**: Qivam
- **TYPE**: commercial API
- **DATA_DOMAIN**: mosque
- **LICENSE**: All rights reserved (SDK licence); API terms not reviewed
- **LICENSE_URL**: https://www.npmjs.com/package/@qivam/client
- **PROVENANCE**: Proprietary service.
- **ACCESS_METHOD**: API (not accessed)
- **REDISTRIBUTION_ALLOWED**: No: SDK licence forbids redistribution; data terms unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: NOT_ALLOWED_FOR_REDISTRIBUTION
- **NOTES**: Not used.

## Datasets already stored (from the manifest)

| Dataset | Source | Licence | Verification status | Public |
|---|---|---|---|---|
| `quran-arabic-uthmani-hafs` | PyPI package quran-text (quran.ws, KFGQPC text) | CC BY 4.0 (VERIFIED_OPEN) | VERIFIED | yes |
| `quran-tajweed-quranws` | npm @quran.ws/tajwid-rules and @quran.ws/tajwid-annotations (rules from Quranpedia) | CC BY 4.0 (VERIFIED_OPEN) | VERIFIED | yes |
| `hadith-bukhari-arabic` | PyPI sahih-al-bukhari | Package declares AGPL-3.0; the original classical text is in the public domain (PD_WORK_OPEN_EDITION_DECLARED) | NEEDS_MANUAL_REVIEW | yes |
| `hadith-muslim-arabic` | PyPI sahih-muslim | Package declares AGPL-3.0; the original classical text is in the public domain (PD_WORK_OPEN_EDITION_DECLARED) | NEEDS_MANUAL_REVIEW | yes |
| `hadith-bukhari-english` | PyPI sahih-al-bukhari 3.1.7 (translation bundled in the package) | Commercially published translation; redistribution rights not established (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `hadith-muslim-english` | PyPI sahih-muslim 1.1.2 (translation bundled in the package) | Commercially published translation; redistribution rights not established (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `hadith-nawawi40-arabic` | npm @kazishariar/nawawi-40-hadith-data | Package declares CC BY 4.0; upstream source not documented. Original text is public domain. (PD_WORK_OPEN_EDITION_DECLARED) | NEEDS_MANUAL_REVIEW | yes |
| `hadith-nawawi40-english` | npm @kazishariar/nawawi-40-hadith-data (bundled translation) | Translator and upstream not documented (PROVENANCE_UNCLEAR) | PROVENANCE_UNCLEAR | no |
| `devotional-hisn-almuslim-arabic` | npm @kazishariar/hisnul-muslim-data | Package declares CC BY 4.0; upstream (selection, numbering, commentary) not documented (PROVENANCE_UNCLEAR) | PROVENANCE_UNCLEAR | no |
| `devotional-adhkar-arabic` | npm @kazishariar/morning-evening-adhkar-data | Package declares CC BY 4.0; upstream not documented (PROVENANCE_UNCLEAR) | PROVENANCE_UNCLEAR | no |
| `devotional-adhkar-english` | npm @kazishariar/morning-evening-adhkar-data (bundled translation) | Translator not documented (PROVENANCE_UNCLEAR) | PROVENANCE_UNCLEAR | no |
| `quran-translation-pickthall` | fawazahmed0/quran-api edition eng-mohammedmarmadu | Public domain (translator died 1936; first published 1930) (PUBLIC_DOMAIN) | VERIFIED | yes |
| `quran-translation-yusufali-1934` | fawazahmed0/quran-api edition eng-yusufaliorig | Public domain (translator died 1953; 1934 edition) (PUBLIC_DOMAIN) | VERIFIED | yes |
| `quran-translations-catalogue` | fawazahmed0/quran-api catalogue (editions.json) | No per-edition licence in the catalogue (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `tafsir-arabic-classical` | spa5k/tafsir_api (data from Quran.com / Tarteel QUL / altafsir.com) | Original works are public domain; the digital editions' own rights are not stated (some carry modern editorial notes) (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `tafsir-arabic-modern` | spa5k/tafsir_api (data from Quran.com / Tarteel QUL / altafsir.com) | Modern works; rights not cleared (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `tafsir-english` | spa5k/tafsir_api (data from Quran.com / Tarteel QUL / altafsir.com) | Modern translations; rights not cleared (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `hadith-grading` | fawazahmed0/hadith-api (info.json, git tag 1) | Unlicense (repository). Rights in the grades compiled from the graders' works are not established. (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `directory-mosques` | GeoAlgeria @geoalgeria/mosquees (composite of Wikidata and OpenStreetMap) | Data: ODbL 1.0 (© OpenStreetMap contributors) and CC0-1.0 (Wikidata); package code: MIT (VERIFIED_OPEN) | VERIFIED | yes |
| `audio-quran-recitations` | No source acquired | Reciter and publisher rights not established (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |

No source of any kind exists yet for 16 datasets (`fiqh-rulings`, `aqeedah`, `seerah`, `terminology`, `library-works`, `history`, `civilization`, `scholar-biographies`, `directory-businesses`, `directory-charities`, `directory-jobs`, `directory-professionals`, `directory-organisations`, `directory-events`, `directory-volunteering`, `directory-health`). They are not listed above because there is nothing to verify; they need owner-supplied data.
