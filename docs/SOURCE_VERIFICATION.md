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
| NEEDS_MANUAL_REVIEW | 4 |
| LICENSE_REQUIRED | 3 |
| PROVENANCE_UNCLEAR | 5 |
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
- **ACCESS_METHOD**: npm tarball, sha512 integrity verified; app/importers/geoalgeria.py (scripts/run_importer.py geoalgeria-mosquees)
- **REDISTRIBUTION_ALLOWED**: Yes, with attribution; share-alike for a derived database (ODbL)
- **COMMERCIAL_USE_ALLOWED**: Yes (ODbL permits commercial use with attribution and share-alike)
- **ATTRIBUTION_REQUIRED**: Yes: © OpenStreetMap contributors; Wikidata CC0 needs none
- **MODIFICATION_ALLOWED**: Yes (ODbL: derivative databases must remain ODbL)
- **UNDERLYING_RIGHTS**: Same as the data: ODbL for OSM-derived records, CC0 for Wikidata records; OSM contributors hold the underlying rights.
- **DATABASE_RIGHTS**: Yes: ODbL is a database licence; share-alike applies to a derived database
- **METADATA_ONLY_SAFE**: Not needed: names and coordinates are the data and are covered by the licence
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: VERIFIED
- **EVIDENCE**: Package LICENSE read (MIT for code; ODbL 1.0 and CC0 for data); dataset-metadata.json read (license URL, citations, dateModified 2026-06-25); README read: build from Wikidata SPARQL and OSM Overpass, ~150 m merge; registry sha512 integrity verified on every download; tarball sha256 5705920a...
- **UNRESOLVED_QUESTIONS**: Whether the platform's directory counts as a 'derived database' needing ODbL share-alike (attribution is shown regardless).; Accuracy of individual records (e.g. the synagogue anomaly) is unverified.
- **NOTES**: Algeria only. Wilaya/commune are derived by centroid, not from the sources. 978 of 20,759 records have no name and are skipped. Denomination kept only where the package took it from an OSM tag.

### Keyword scan of the npm registry for Islamic datasets - NEEDS_MANUAL_REVIEW

`npm-registry-scan`

- **SOURCE_NAME**: Keyword scan of the npm registry for Islamic datasets
- **SOURCE_URL**: https://registry.npmjs.org/
- **OWNER**: npm
- **TYPE**: discovery method
- **DATA_DOMAIN**: all domains
- **LICENSE**: n/a
- **LICENSE_URL**: https://registry.npmjs.org/
- **PROVENANCE**: About 40 search queries (hadith, fiqh, seerah, aqeedah, mosque, charity, reciter, glossary, scholar, history ...) returned 491 relevant package names; data-bearing ones were opened and their LICENSE and README read.
- **ACCESS_METHOD**: npm search API
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **MODIFICATION_ALLOWED**: n/a
- **UNDERLYING_RIGHTS**: n/a
- **DATABASE_RIGHTS**: n/a
- **METADATA_ONLY_SAFE**: n/a
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: NEEDS_MANUAL_REVIEW
- **EVIDENCE**: /tmp scan outputs reviewed 2026-10-01; tarballs of @geoalgeria/mosquees, @al-mabsut/muslimah, sacred_texts, arabic-dictionary, @qivam/client, @trydaleel/domain-islamic-hadith read
- **UNRESOLVED_QUESTIONS**: Packages published after 2026-10-01 are not covered.
- **NOTES**: Only @geoalgeria/mosquees (used) and the already-held @quran.ws and @kazishariar packages qualified; the rest were API wrappers, UI kits or calendar/prayer-time libraries. Re-scanned 2026-10-03 with 23 search terms (fiqh, sirah, aqeedah, glossary, terminology, scholars, history, calendar events, masjid, halal, waqf, charities, zakat, recitation ...): 156 packages; none is a source-backed dataset for the empty domains. Hits were calculators, API clients, MCP servers over third-party sites (turath.io, Shamela-derived), UI kits and fonts.

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
- **MODIFICATION_ALLOWED**: Yes (Apache-2.0) for the code
- **UNDERLYING_RIGHTS**: Code author
- **DATABASE_RIGHTS**: Not applicable
- **METADATA_ONLY_SAFE**: Not applicable
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: NEEDS_MANUAL_REVIEW
- **EVIDENCE**: package contents read: code (grade taxonomy, authority normalisation); no README
- **UNRESOLVED_QUESTIONS**: Source of the 'authority' list.
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
- **MODIFICATION_ALLOWED**: Per dataset
- **UNDERLYING_RIGHTS**: The owner must state them
- **DATABASE_RIGHTS**: Per dataset
- **METADATA_ONLY_SAFE**: Per dataset
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: NEEDS_MANUAL_REVIEW
- **EVIDENCE**: Admin upload and adapters implemented and tested
- **UNRESOLVED_QUESTIONS**: Everything: no dataset has been supplied.
- **NOTES**: The pipeline is ready; each dataset enters as staged until rights are confirmed.

### Systematic scan of the PyPI project index for Islamic datasets - NEEDS_MANUAL_REVIEW

`pypi-index-scan`

- **SOURCE_NAME**: Systematic scan of the PyPI project index for Islamic datasets
- **SOURCE_URL**: https://pypi.org/simple/
- **OWNER**: PyPI
- **TYPE**: discovery method
- **DATA_DOMAIN**: all domains
- **LICENSE**: n/a
- **LICENSE_URL**: https://pypi.org/simple/
- **PROVENANCE**: All 903,694 project names were matched against Islamic keywords (hadith, quran, tafsir, fiqh, sunnah, seerah, aqeedah, mosque, ...); 89 plausible names were reviewed by metadata, and the data-bearing ones by wheel contents.
- **ACCESS_METHOD**: PyPI JSON simple index
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **MODIFICATION_ALLOWED**: n/a
- **UNDERLYING_RIGHTS**: n/a
- **DATABASE_RIGHTS**: n/a
- **METADATA_ONLY_SAFE**: n/a
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: NEEDS_MANUAL_REVIEW
- **EVIDENCE**: pypi-simple.json (44 MB) downloaded 2026-10-01 and filtered; metadata of 20 candidates read; wheels of openiti, hadith and islamlib downloaded and inspected
- **UNRESOLVED_QUESTIONS**: Packages that wrap remote APIs were not followed to the remote service (unreachable).
- **NOTES**: Reviewed: ahadith (GPL, API wrapper), hadith (provenance unclear), isnad* (software), openiti (code only), pytafseer/quran/sunnah-api/widequran (API wrappers), kaeshur-quran (app data, Kashmiri), quran-text (already used). No new usable domain dataset was found.

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
- **ACCESS_METHOD**: raw.githubusercontent.com; app/importers/hadith_grades.py (scripts/run_importer.py hadith-api-grades)
- **REDISTRIBUTION_ALLOWED**: Unknown: the Unlicense covers only the repository author's own work
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Recommended
- **MODIFICATION_ALLOWED**: Unknown
- **UNDERLYING_RIGHTS**: Held by the graders (e.g. al-Albani's and Zubair Ali Za'i's published works) and the publishers/compilers on al-maktaba.org; not addressed by the repository licence.
- **DATABASE_RIGHTS**: Possible: a systematic extraction of grades for ~21,000 hadiths from compiled web editions
- **METADATA_ONLY_SAFE**: Probably safe as bibliographic pointers (collection, number, grader, work), but the grade labels themselves are the compiled content; not decided
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: LICENSE_REQUIRED
- **EVIDENCE**: LICENSE read verbatim: Unlicense; References.md read: grades taken from al-maktaba.org books (ids listed) and zubairalizai.com; CONTRIBUTING.md/README.md read: no statement about rights in the data; database/originals file names end in 'scrapped.txt' (e.g. englishtirmidhiscrapped.txt, 1.5 MB), evidencing scraping; al-maktaba.org, zubairalizai.com and the maktaba-grades-backup site are unreachable from the build environment
- **UNRESOLVED_QUESTIONS**: Do individual grade labels (short factual judgements) attract copyright, or only the compilation (database right)?; Do the sites' terms permit extraction and republication?; Are the grade values accurate relative to the printed works (not checked)?; A grader's grade may differ between editions of their work.
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
- **MODIFICATION_ALLOWED**: Unknown
- **UNDERLYING_RIGHTS**: Translators' and publishers' rights; not addressed
- **DATABASE_RIGHTS**: Unknown
- **METADATA_ONLY_SAFE**: Edition metadata yes; text no
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: LICENSE_REQUIRED
- **EVIDENCE**: editions.json read: author 'Unknown' for most editions; some name Muhsin Khan, Abdul Hamid Siddiqui, Imam Nawawi, Shah Waliullah Dehlawi; only two editions state a source (isnad.link)
- **UNRESOLVED_QUESTIONS**: Translator and publisher permission for each edition.
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
- **MODIFICATION_ALLOWED**: Code yes
- **UNDERLYING_RIGHTS**: mp3quran.net and reciters
- **DATABASE_RIGHTS**: Unknown
- **METADATA_ONLY_SAFE**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: LICENSE_REQUIRED
- **EVIDENCE**: npm metadata: MIT for the wrapper code
- **UNRESOLVED_QUESTIONS**: mp3quran.net terms.
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
- **MODIFICATION_ALLOWED**: Unknown for the content
- **UNDERLYING_RIGHTS**: Author's own guidance; sources not cited
- **DATABASE_RIGHTS**: Not applicable
- **METADATA_ONLY_SAFE**: Titles only
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **EVIDENCE**: package.json: ISC, author Mufti Khalil Johnson; raw repository: no LICENSE file (404); content page read: guidance in markdown with no cited work, edition or page
- **UNRESOLVED_QUESTIONS**: Which works the rulings come from.; Whether ISC (a software licence) was intended for the content.
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
- **MODIFICATION_ALLOWED**: Code yes (MIT)
- **UNDERLYING_RIGHTS**: Unknown
- **DATABASE_RIGHTS**: Unknown
- **METADATA_ONLY_SAFE**: Not applicable
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **EVIDENCE**: npm metadata only
- **UNRESOLVED_QUESTIONS**: Authority behind the occasion lists.
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
- **MODIFICATION_ALLOWED**: Unknown
- **UNDERLYING_RIGHTS**: Arabic classical text: public domain; edition and English translation: unattributed (the English text appears to be a published translation)
- **DATABASE_RIGHTS**: Unknown
- **METADATA_ONLY_SAFE**: Collection and chapter titles only
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **EVIDENCE**: npm metadata: AGPL-3.0 declared by 'muhammadsaadamin'; README read: no source, translator or edition named; data file (gzip JSON) read: Arabic plus English narrator/text, no attribution
- **UNRESOLVED_QUESTIONS**: Where the English text came from and who holds rights in it.; An AGPL declaration cannot grant rights the packager does not hold.
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
- **MODIFICATION_ALLOWED**: Unknown
- **UNDERLYING_RIGHTS**: Not established: individual texts come from several sources and may carry their own terms
- **DATABASE_RIGHTS**: Unknown
- **METADATA_ONLY_SAFE**: Unknown: the metadata CSV could not be read, so its terms are not known
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **EVIDENCE**: RELEASE repository README (master) read: cites Zenodo doi 10.5281/zenodo.3082463; states no licence; LICENSE, LICENSE.md, license.txt return 404 on master and main; PyPI package 'openiti' 0.1.6: MIT for the Python code; its METADATA says nothing about corpus licensing; Zenodo, GitHub tree and metadata CSV unreachable from the build environment
- **UNRESOLVED_QUESTIONS**: The corpus and metadata licence (read the Zenodo record or the project's own statement).; Whether non-commercial or share-alike terms apply.
- **NOTES**: Not used. A catalogue of authors, works and death dates would fill several domains; it needs its licence confirmed first. 2026-10-03: the RELEASE README was read (raw.githubusercontent.com): it states no licence and points to Zenodo and the KITAB site, which are unreachable here. No licence evidence, so the corpus stays PROVENANCE_UNCLEAR.

### PyPI hadith 0.0.2a1 (Umma Open Source) - PROVENANCE_UNCLEAR

`pypi-hadith-umma1`

- **SOURCE_NAME**: PyPI hadith 0.0.2a1 (Umma Open Source)
- **SOURCE_URL**: https://pypi.org/project/hadith/
- **OWNER**: Umma Open Source
- **TYPE**: packaged dataset
- **DATA_DOMAIN**: hadith (Arabic collections)
- **LICENSE**: MIT classifier; metadata says 'License: UNKNOWN'
- **LICENSE_URL**: https://pypi.org/project/hadith/
- **PROVENANCE**: Wheel contains CSV files of Sahih al-Bukhari, Sahih Muslim, the four Sunan, Musnad Ahmad, Muwatta Malik and al-Darimi with no stated edition, source or compiler.
- **ACCESS_METHOD**: pip download (wheel read, not imported)
- **REDISTRIBUTION_ALLOWED**: Unknown
- **COMMERCIAL_USE_ALLOWED**: Unknown
- **ATTRIBUTION_REQUIRED**: Unknown
- **MODIFICATION_ALLOWED**: Unknown
- **UNDERLYING_RIGHTS**: Classical Arabic: public domain; this edition: unknown
- **DATABASE_RIGHTS**: Unknown
- **METADATA_ONLY_SAFE**: Collection names only
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: PROVENANCE_UNCLEAR
- **EVIDENCE**: wheel METADATA read: license UNKNOWN, description 'UNKNOWN'; no README or LICENSE in the wheel; CSV header and first rows read: text only, no isnad split, no numbering metadata
- **UNRESOLVED_QUESTIONS**: Which edition and who typed or scraped it.
- **NOTES**: Not imported. The classical Arabic texts are public domain, but this digital edition has no stated origin.

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
- **MODIFICATION_ALLOWED**: Per terms
- **UNDERLYING_RIGHTS**: Employers and feed operators
- **DATABASE_RIGHTS**: Per terms
- **METADATA_ONLY_SAFE**: Per terms
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **EVIDENCE**: api.adzuna.com and usajobs.gov did not answer on 2026-10-01
- **UNRESOLVED_QUESTIONS**: Keys, terms, and whether republication is allowed.
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
- **MODIFICATION_ALLOWED**: Unknown until read
- **UNDERLYING_RIGHTS**: Government bodies; licence not re-read here
- **DATABASE_RIGHTS**: Unknown until read
- **METADATA_ONLY_SAFE**: Registration data is the data
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **EVIDENCE**: register-of-charities.charitycommission.gov.uk and irs.gov did not answer on 2026-10-01
- **UNRESOLVED_QUESTIONS**: Licence per register.; A faith field is required before listing as Muslim charities.
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
- **MODIFICATION_ALLOWED**: Unknown until read
- **UNDERLYING_RIGHTS**: Per catalogue
- **DATABASE_RIGHTS**: Unknown until read
- **METADATA_ONLY_SAFE**: Intended use: metadata and external links only
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **EVIDENCE**: openlibrary.org, archive.org, gutenberg.org did not answer on 2026-10-01
- **UNRESOLVED_QUESTIONS**: Licence of each catalogue's metadata.
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
- **MODIFICATION_ALLOWED**: Yes, share-alike
- **UNDERLYING_RIGHTS**: OSM contributors (ODbL)
- **DATABASE_RIGHTS**: Yes (ODbL)
- **METADATA_ONLY_SAFE**: Not needed
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **EVIDENCE**: Overpass status endpoint did not answer (URLError) from the build environment on 2026-10-01; ODbL terms are the project's published licence (not re-read in this environment: openstreetmap.org unreachable)
- **UNRESOLVED_QUESTIONS**: Usage policy of the public Overpass instance for the production server (small boxes, no repeated runs).
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
- **MODIFICATION_ALLOWED**: Unknown
- **UNDERLYING_RIGHTS**: Reciters and publishers
- **DATABASE_RIGHTS**: Unknown
- **METADATA_ONLY_SAFE**: Reciter names and surah/ayah mapping could be metadata; links need the host's terms
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **EVIDENCE**: everyayah.com, mp3quran.net, api.quran.com, cdn.islamic.network did not answer on 2026-10-01
- **UNRESOLVED_QUESTIONS**: Each host's redistribution and hotlinking terms.
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
- **MODIFICATION_ALLOWED**: Unknown
- **UNDERLYING_RIGHTS**: Translators' and publishers' rights; sunnah.com terms not read
- **DATABASE_RIGHTS**: Unknown
- **METADATA_ONLY_SAFE**: Unknown
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **EVIDENCE**: sunnah.com and api.sunnah.com did not answer from the build environment
- **UNRESOLVED_QUESTIONS**: API terms, key, and whether republication is allowed.
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
- **MODIFICATION_ALLOWED**: Yes
- **UNDERLYING_RIGHTS**: CC0 dedication for structured data (not re-read here)
- **DATABASE_RIGHTS**: CC0
- **METADATA_ONLY_SAFE**: Yes
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: TECHNICALLY_UNAVAILABLE
- **EVIDENCE**: query.wikidata.org and www.wikidata.org did not answer from the build environment on 2026-10-01
- **UNRESOLVED_QUESTIONS**: Per-statement accuracy; every record must cite its Q-number and retrieval date.
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
- **MODIFICATION_ALLOWED**: No
- **UNDERLYING_RIGHTS**: Qivam
- **DATABASE_RIGHTS**: Presumed
- **METADATA_ONLY_SAFE**: No
- **LAST_VERIFIED**: 2026-10-01
- **VERIFICATION_STATUS**: NOT_ALLOWED_FOR_REDISTRIBUTION
- **EVIDENCE**: @qivam/client LICENSE read: all rights reserved; no modification, redistribution or derivative works without permission
- **UNRESOLVED_QUESTIONS**: API terms (not reviewed).
- **NOTES**: Not used.

## Datasets already stored (from the manifest)

| Dataset | Source | Licence | Verification status | Public |
|---|---|---|---|---|
| `quran-arabic-uthmani-hafs` | PyPI package quran-text (quran.ws, KFGQPC text) | CC BY 4.0 (VERIFIED_OPEN) | VERIFIED | yes |
| `quran-tajweed-quranws` | npm @quran.ws/tajwid-rules and @quran.ws/tajwid-annotations (rules from Quranpedia) | CC BY 4.0 (VERIFIED_OPEN) | VERIFIED | yes |
| `hadith-bukhari-arabic` | PyPI sahih-al-bukhari | Package declares AGPL-3.0; the original classical text is in the public domain (PROVENANCE_UNCLEAR) | PROVENANCE_UNCLEAR | no |
| `hadith-muslim-arabic` | PyPI sahih-muslim | Package declares AGPL-3.0; the original classical text is in the public domain (PROVENANCE_UNCLEAR) | PROVENANCE_UNCLEAR | no |
| `hadith-bukhari-english` | PyPI sahih-al-bukhari 3.1.7 (translation bundled in the package) | Commercially published translation; redistribution rights not established (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `hadith-muslim-english` | PyPI sahih-muslim 1.1.2 (translation bundled in the package) | Commercially published translation; redistribution rights not established (LICENSE_REQUIRED) | LICENSE_REQUIRED | no |
| `hadith-nawawi40-arabic` | npm @kazishariar/nawawi-40-hadith-data | Package declares CC BY 4.0; upstream source not documented. Original text is public domain. (PROVENANCE_UNCLEAR) | PROVENANCE_UNCLEAR | no |
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
