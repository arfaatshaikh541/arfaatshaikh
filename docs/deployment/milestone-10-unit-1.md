# Milestone 10 Unit 1: Deployment and Release Hardening

This unit establishes fail-closed production release contracts. Production requires HTTPS, secure cookies, an immutable image digest, a managed secrets provider, the current migration revision, health/readiness evidence, a successful encrypted backup restore rehearsal, rollback verification, and a passing AI release gate.

The database records deployment environments, releases, verification evidence, and restore rehearsals. Policy endpoints validate configuration and release readiness. These contracts do not claim that a live cloud deployment or restore has occurred.
