# Milestone 12 Unit 4: Federation Governance and Acceptance

This unit closes Milestone 12 with governance around peer attestations, synchronization-policy changes, security incidents, quarantine release, and final federation acceptance.

## Safety properties

- Trusted peers require independent, expiring attestations.
- Sensitive-content access expansion requires separation of request and approval.
- High and critical incidents require node suspension, credential revocation, and transfer cancellation.
- Critical incidents cannot be dismissed.
- Quarantine release requires resolved incidents, clean integrity verification, credential rotation, independent approval, and zero unresolved drift.
- Portable readiness is explicitly separated from production readiness. Live network validation is required for production acceptance.

## Portable acceptance

Portable tests validate deterministic policy behavior, migration renderability, compilation, and archive integrity. They do not prove live federation, remote cryptographic identity, real worker execution, or production networking.
