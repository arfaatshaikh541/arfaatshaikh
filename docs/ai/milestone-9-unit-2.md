# Milestone 9 Unit 2: Multilingual Intelligence

Supports Arabic, English, Urdu, Hindi, and transliteration while keeping claim identity, evidence fingerprints, citation order, and source attribution immutable across languages.

## Safety gates

- Translation never creates new religious evidence.
- Every translated claim retains the canonical claim identifier and citations.
- Arabic/Urdu script checks fail closed.
- Low-confidence translations require human review.
- Urdu, Hindi, and transliteration require human language review before publication.
- Source fingerprints are checked before alignment.

## Deferred deployment validation

Live PostgreSQL, production translation models, native-speaker review, browser E2E, queue workers, and load testing remain outside portable acceptance.
