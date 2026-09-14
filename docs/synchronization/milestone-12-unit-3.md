# Milestone 12 Unit 3: Integrity Snapshots and Drift Reconciliation

## Scope
This unit adds deterministic corpus snapshots, partition digests, drift localization, governed repair plans, and post-repair integrity verification.

## Safety properties
- Snapshot roots are built from canonical, ordered content fingerprints.
- Duplicate partitions and unordered item inputs fail closed.
- Drift is localized to matching, divergent, and missing partitions.
- Sensitive Qur'an, Hadith, Tafsir, and Fiqh replacements cannot run automatically.
- Divergent sensitive content requires scholarly approval.
- A snapshot is verified only when every partition is checked, the root matches, and no unresolved drift remains.

## Persistence
Migration `20260726_0048` creates snapshots, partition digests, drift reports, repair plans, and integrity-verification evidence.

## Portable acceptance boundary
This unit validates deterministic policy and schema behavior. It does not claim live cross-node corpus hashing, production object-store scans, remote signature verification, or real repair execution.
