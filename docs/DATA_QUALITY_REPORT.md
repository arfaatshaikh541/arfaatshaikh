# Data quality report

Generated 2026-10-01T20:16:49.722789+00:00 by `scripts/data_quality_report.py` from the live database. It reports problems and repairs nothing.

## Records per domain

| Source of count | Total | Published (visible) | Hidden |
|---|---|---|---|
| `dl:mosque` | 19781 | 19776 | 5 |
| `hadith_narrations` | 15110 | 14778 | 332 |
| `kr:hadith_grading` | 21185 | 0 | 21185 |
| `quran_ayahs` | 6236 | 6236 | 0 |
| `tafsir_entries` | 182320 | 0 | 182320 |

## Knowledge records

| Measure | Count |
|---|---|
| total | 21185 |
| published | 0 |
| hidden | 21185 |
| unverified | 21185 |
| missing names | 0 |
| missing source ids | 0 |
| missing provenance | 0 |
| provenance status unclear | 0 |
| without licence metadata | 0 |
| without verification status | 0 |
| invalid urls | 0 |
| orphaned relationships | 0 |
| grader labels differ | 15596 |

## Directory listings

| Measure | Count |
|---|---|
| total | 19781 |
| published visible | 19776 |
| hidden | 5 |
| unverified | 19781 |
| missing names | 0 |
| missing source ids | 0 |
| missing provenance | 0 |
| duplicates linked | 5 |
| invalid urls | 0 |
| expired | 0 |
| without licence metadata | 0 |
| without verification status | 0 |

## Duplicates and conflicts (candidates for human review)

| Kind | Count |
|---|---|
| duplicate candidates | 0 |
| similar names | 38 |
| co located different | 282 |
| denomination conflicts | 0 |
| non mosque names | 8 |

## Coverage of visible listings (country:type)

| Country:type | Visible listings |
|---|---|
| DZ:mosque | 19776 |

## Source-quality notes (retained unchanged)

- `geoalgeria:16-0918` (directory-mosques): One record carries the name "Grande synagogue d'Alger" and the Arabic name "مسجد ابن فارس" (a mosque), and is classified as a mosque. Its Wikidata item is Q5600070 and its OpenStreetMap object is way/1173895775. Unknown: Why the two labels disagree is not stated by the source; the building may have changed use, or one label may be wrong. This was not resolved. Action: retained unchanged and shown as 'Not verified'; reported by the non_mosque_names check. Record still present: True.
- `geoalgeria:48-0139` (directory-mosques): Seven further records have English names containing 'Chapel' or 'Temple' (for example "Mercy Chapel in Oued Rhiou", "Chapel Omar ibn al-Khattab may Allah be pleased with him in Djelfa") while being classified as mosques. Unknown: Whether these are English renderings of an Arabic or French place-of-prayer word, or genuine errors, is not established by the source or by this project. Action: retained unchanged and shown as 'Not verified'; listed by the non_mosque_names check as candidates for human review. Record still present: True.
