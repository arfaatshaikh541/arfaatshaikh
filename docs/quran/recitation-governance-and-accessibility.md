# Recitation governance and accessibility

Milestone 3 stores recitation metadata and verified HTTPS object references only. It does not bundle audio or infer licences.

A recitation edition links to an approved Source Registry edition and records the reciter, riwayah, format and mandatory attribution. Ayah audio records carry SHA-256, byte size and duration. Publication rechecks source approval and fails closed if the source is revoked or no audio records exist.

Public playback exposes only published recitations and audio attached to published ayahs in the canonical Qur'an edition. Account playback state is private, CSRF-protected and constrained to the audio duration.

Reader accessibility includes native HTML audio controls, keyboard-reachable controls, visible focus, stable ayah anchors, reduced-motion support, bilingual labels, RTL Arabic, repeat controls and Alt+Arrow surah navigation.

No recitation audio is included in the repository.
