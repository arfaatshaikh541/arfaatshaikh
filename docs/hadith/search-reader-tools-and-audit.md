# Hadith search, reader tools, and Milestone 4 audit

## Search safety
Search returns only published narrations from published collections. Filters may select collection, attributed grader, normalized grading label, and transmitted narrator name. A normalized label is a filter, never a platform verdict.

## Narrator provenance
Narrator profiles preserve canonical and Arabic names, aliases, disambiguation notes, and the exact Source Registry passage used as identity evidence. Unresolved isnad nodes remain unresolved rather than being force-linked.

## Private reader state
Bookmarks and reading history are account scoped. Mutations require an authenticated server-side session and CSRF validation. History stores the latest read time and a read counter without exposing another account's activity.

## Isnād presentation
The public isnād endpoint returns ordered nodes, transmission terms, textual transmitted names, and optional normalized narrator links. The interface must render this as an ordered chain, not as an authenticity score.

## Citation exports
Authenticated users can export one published narration as canonical JSON, CSV, or plain text. Each payload receives a SHA-256 digest and an append-only export record. Exports preserve Arabic matn and canonical reference and do not imply endorsement of a grading opinion.

## Completion boundary
No hadith, chain, narrator biography, translation, or grading is bundled with the repository. Live database migration, production search performance, browser accessibility, and real corpus import remain operational verification tasks.
