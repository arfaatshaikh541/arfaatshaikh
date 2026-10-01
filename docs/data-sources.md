# Content sources, licences and verification

The authoritative, machine-checked record of every source is **`data/source-manifest.json`**. The human-readable table
generated from it is **[`DATA_READINESS.md`](DATA_READINESS.md)**: source, purpose, licence, provenance, verification,
public/private status, import method, last check and the remaining action for each dataset. This page explains how to
read it and what the platform does with each status.

## What is public by default

A production deployment shows only content whose licence is clearly open **and** whose checks passed:

| Public | Source | Licence |
|---|---|---|
| Qur'an, Arabic (Uthmani, Hafs) | PyPI `quran-text` 0.1.0 | CC BY 4.0 (verified) |
| Tajweed rules and spans | npm `@quran.ws/tajwid-*` 0.1.0 | CC BY 4.0 (verified) |
| Sahih al-Bukhari, Sahih Muslim (Arabic) | PyPI packages | Original texts are public domain; the packages declare AGPL-3.0 (owner to confirm, see `NEEDS_REVIEW`) |
| Forty Hadith (Arabic) | npm `@kazishariar/nawawi-40-hadith-data` | Declared CC BY 4.0, upstream undocumented; wording cross-checked against the published hadith text |
| Qur'an translations by Pickthall (1930) and Yusuf Ali (1934 edition) | fawazahmed0/quran-api | Public domain (translators died 1936 / 1953) |

Everything else is **staged**: stored with full provenance but hidden from readers, search, the assistant and the
knowledge graph, and shown to visitors as *"Source not currently available for public publication."* This covers the
English hadith translations, Hisn al-Muslim, the adhkar, all 54 tafsir editions (Arabic and English), and 482 further
Qur'an translations in 97 languages. See `DATA_READINESS.md` for the reason and the remaining action of each.

## How the owner publishes a staged source

1. Obtain permission (or verify an open licence) for the specific work.
2. In the admin area (**Data & trust**) or through `POST /api/v1/admin/datasets/{id}/action`: *mark verified* (with a
   note), then *publish* with who confirmed, when, and on what basis. This is stored and audited.
3. Or edit the dataset's entry in `data/source-manifest.json` (`rights_confirmation`, licence status) and run
   `uv run python scripts/sync_manifest.py`.

`scripts/publish_staged.py` remains available for operators who prefer a command line.

## Deliberately not imported

- Qur'an translations by non-Muslim translators (Arberry, Palmer, Sale, Rodwell, Dawood) and by groups outside
  mainstream Islam (Monotheist Group, Ahmadiyya or Rashad Khalifa translations): not stored.
- One Urdu translation (`urd-muhammadtahirul`): 217 empty verses, below the 99% completeness bar.
- Tafsir catalogue items that are not commentary (dependency graphs, qira'at manuals, word tables), an edition that is
  mislabelled (`ar-tafseer-tanwir-al-miqbas` contains the Ibn Ashur text), and editions that failed verification
  (insufficient coverage, or entries that did not align with their ayah). Details in `DATA_READINESS.md`.
- Any dataset whose licence or provenance could not be established.

## Still without a source (empty states, ready for data)

Fiqh, aqeedah, seerah, hadith grading, terminology, library, history, civilization, scholar biographies, recitation audio
and every directory (mosques, businesses, charities, jobs, professionals, organisations, events, volunteering, health)
have **no dataset loaded**. Their schemas, importers, admin workflow and empty-state pages exist
(`docs/data-contracts.md`); nothing is written from memory. Alternatives that were investigated, and why they were or
were not used, are listed in `DATA_READINESS.md`.

## Re-run order on a fresh database

```
alembic upgrade head
python scripts/import_real_evidence.py     python scripts/import_quran_reader.py
python scripts/import_hadith_reader.py     python scripts/import_tajweed.py
python scripts/import_tafsir.py            python scripts/import_translations.py    # long
python scripts/import_tafsir_catalogue.py  # long
python scripts/sync_manifest.py            # registers the manifest and applies publication decisions
python scripts/build_knowledge_graph.py    # sourced relationships between published entities
python scripts/validate_data.py            # must print PASS for every rule before a release
```
