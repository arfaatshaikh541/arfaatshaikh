# Content sources, licences and verification

Every text in the platform enters through the source registry (licence, integrity digest, review,
attribution). This table records where each came from and what is **not** verified. Anything marked
"confirm before public launch" needs the rights holder's terms checked by a person.

| Content | Source | Declared licence | How it was verified | Confirm before launch |
|---|---|---|---|---|
| Qur'an (Arabic, Uthmani, Hafs) | PyPI `quran-text` 0.1.0 (quran.ws, KFGQPC text) | CC BY 4.0 | 114 surahs / 6,236 ayahs; known ayahs spot-checked | - |
| Tajweed rules + spans | npm `@quran.ws/tajwid-rules`, `@quran.ws/tajwid-annotations` 0.1.0 (rules from Quranpedia) | CC BY 4.0 | npm sha512 integrity; all 147,255 spans in bounds; all 3,839 qalqalah spans land on a qalqalah letter | - |
| Sahih Muslim (Arabic + English) | PyPI `sahih-muslim` 1.1.2 | AGPL-3.0 (package) | Hadith 1 matches the Siddiqui wording; PyPI sha256 checked | English translation rights |
| Sahih al-Bukhari (Arabic + English) | PyPI `sahih-al-bukhari` 3.1.7 | AGPL-3.0 (package) | Hadith 1 matches the Muhsin Khan wording; PyPI sha256 checked | English translation rights (commercially published translation) |
| Forty Hadith of al-Nawawi | npm `@kazishariar/nawawi-40-hadith-data` 1.0.3 | CC BY 4.0 (declared, upstream not documented) | Arabic cross-checked against Bukhari/Muslim text (41 of 42 entries found) | Translation/upstream rights |
| Hisn al-Muslim (Arabic only) | npm `@kazishariar/hisnul-muslim-data` 1.0.3 | CC BY 4.0 (declared, upstream not documented) | Each entry is labelled: 67 cross-checked against the Qur'an, 109 against Bukhari/Muslim, the rest not cross-checked. The package's machine-made transliteration is not used | Upstream rights |
| Morning/evening adhkar | npm `@kazishariar/morning-evening-adhkar-data` 1.0.3 | CC BY 4.0 (declared, upstream not documented) | Arabic cross-check label per entry; source cited per entry | Translation/upstream rights |
| Tafsir al-Jalalayn (Arabic) | github.com/spa5k/tafsir_api (from Quran.com / Tarteel QUL) | Original work public domain; edition rights not stated | Entries quote their own ayah (98.0% aligned); abort threshold 90% | Edition rights |
| Tafsir Ibn Kathir (Arabic) | same | Original work public domain; edition rights not stated | 99.2% aligned; identical consecutive ayahs merged into ranges | Edition rights |
| Tafsir al-Jalalayn (English) | same | Modern translation; recorded as non-commercial | 6,010 of 6,010 entries align ayah-by-ayah with the Arabic | Translator credit and terms |
| Qur'an translations, 97 languages (484 editions) | github.com/fawazahmed0/quran-api (`editions.json` catalogue) | **No per-edition licence in the catalogue.** Only Pickthall (d. 1936) and Yusuf Ali's 1934 original are public domain and **published**; the other 482 are **staged** (stored, hidden) | Each edition has exactly 6,236 verses, numbering identical to the Arabic text, at least 99% non-empty; sha256 of each file recorded | Publisher/translator permission for every staged edition |
| Arabic tafsirs (45 editions, incl. Jalalayn and Ibn Kathir) | github.com/spa5k/tafsir_api (Quran.com / Tarteel QUL / altafsir.com) | Classical works (author d. before 1340 AH) are **published** as public-domain works; digital-edition rights unverified. Modern works are **staged** | Coverage of the Qur'an and alignment to the ayah (quoted ayah or at least 60% word overlap, 80% of entries) checked per edition; partial works are labelled with their coverage | Edition rights; modern authors' permission |
| English tafsirs (9 editions) | same | Modern translations: all **staged** | Coverage checked; nothing published | Translator/publisher permission |

## Deliberately not imported
- English Ibn Kathir (abridged): commercially published translation.
- Qur'an translations by non-Muslim translators (Arberry, Palmer, Sale, Rodwell, Dawood) and by groups outside mainstream Islam (the Monotheist Group editions, Ahmadiyya or Rashad Khalifa translations): excluded, not stored. Listed in the import report.
- One Urdu translation (`urd-muhammadtahirul`): 217 empty verses, below the 99% bar.
- Tafsir catalogue items that are not commentary (dependency graphs, qira'at manuals, word tables) and an edition mislabelled as Tanwir al-Miqbas (its file is the Ibn Ashur text).
- Tafsir editions that failed verification or are too incomplete in the source: Kashf al-Asrar, Tustari, Asbab al-Nuzul (al-Wahidi) - under 20% coverage; al-Kashshaf, al-Durr al-Masun, Jadwal fi I'rab, Tha'alibi (duplicate), Mukhtasar (Arabic), Sa'di (this slug; another Sa'di edition passed) and al-Siraj fi Gharib al-Qur'an - text did not align to its ayah.
- Any dataset whose licence could not be read from the package or repository.

## Still without a source
Fiqh, aqeedah, seerah, hadith grading, terminology, library, scholars and fatwas, history and
civilisation data, directories (mosques, jobs, businesses, charities) and family/legal guidance.
No reachable open dataset with verifiable provenance was found, and text is never written from
memory.

Re-run order on a fresh database: `alembic upgrade head`, then `import_real_evidence.py`,
`import_quran_reader.py`, `import_hadith_reader.py`, `import_tajweed.py`, `import_tafsir.py`,
`import_translations.py` (long: hundreds of downloads), `import_tafsir_catalogue.py`.

## Published vs staged
Staged content is in the database with full provenance but does not appear in readers or search.
After you have confirmed permission for a work, publish it with
`publish_staged.py --translations <key> --i-have-permission` (or `--tafsir <key>`; `--list` shows counts;
`--unpublish` hides it again). Publishing does not change the licence record in the registry.
