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

## Deliberately not imported
- English Ibn Kathir (abridged): commercially published translation.
- Tafsir al-Qurtubi: alignment to the ayah was only 70%, below the 90% bar.
- Any dataset whose licence could not be read from the package or repository.

## Still without a source
Fiqh, aqeedah, seerah, hadith grading, terminology, library, scholars and fatwas, history and
civilisation data, directories (mosques, jobs, businesses, charities) and family/legal guidance.
No reachable open dataset with verifiable provenance was found, and text is never written from
memory.

Re-run order on a fresh database: `alembic upgrade head`, then `import_real_evidence.py`,
`import_quran_reader.py`, `import_hadith_reader.py`, `import_tajweed.py`, `import_tafsir.py`.
