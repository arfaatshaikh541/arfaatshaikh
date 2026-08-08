# Disaster Recovery

## Principle

A backup that has never been restored is a hypothesis, not a backup. Every control
below has a corresponding scheduled drill in `docs/testing/README.md` (categories 21–22)
with logged pass/fail results.

## Backup scope & method

| Data class | Method | Frequency | Retention |
|---|---|---|---|
| World Model (Postgres) | Encrypted logical + WAL continuous archiving | Continuous (WAL) + daily full | 35 days rolling, monthly archived 1yr |
| Object storage (documents, media) | Versioned bucket + encrypted snapshot | Continuous (versioning) + daily snapshot | 35 days rolling |
| Credential Vault | Encrypted seal-key-backed snapshot | Daily | 35 days rolling |
| Audit log (hash-chained) | Append-only, replicated to independent immutable storage (write-once) | Continuous | Indefinite (legal/forensic value) |
| Infrastructure config (IaC) | Git history | Every change | Indefinite |
| Model Router / policy configuration | Git history (policy-as-code) | Every change | Indefinite |

Backups are encrypted with a key **separate** from the primary data-encryption keys, and
a copy of the offline recovery key material is held by the owner outside the primary
infrastructure (e.g., a hardware security key + printed/sealed recovery phrase in secure
physical storage) — so a full compromise or provider loss of the primary environment
does not also destroy the ability to recover.

## Recovery objectives (illustrative starting targets, tune per business criticality)

- **RPO (Recovery Point Objective)**: ≤ 5 minutes for World Model (via WAL streaming),
  ≤ 24 hours for object storage/vault snapshots.
- **RTO (Recovery Time Objective)**: ≤ 4 hours for full platform restore on
  replacement infrastructure, assuming IaC-driven rebuild.

## Recovery procedure (runbook outline)

1. Provision replacement infrastructure from IaC (`/infra`) — no manual clicking.
2. Restore Vault from encrypted snapshot; unseal using offline recovery key material
   (owner-present step, by design — this is a RED-tier-adjacent operation).
3. Restore Postgres from latest WAL-consistent point.
4. Restore object storage from latest snapshot/version state.
5. Restore/replay audit log from immutable independent storage; verify hash chain
   integrity before trusting it.
6. Redeploy services from signed release artifacts (`docs/security/README.md#supply-
   chain-security`), pinned to the last known-good versions.
7. Run integration + smoke test suite before reconnecting any external connectors.
8. Reconnect connectors one at a time, health-checked, starting with read-only ones.
9. Kill switch remains engaged until the Security Guardian and owner both confirm
   integrity — recovery does not auto-resume autonomous action.
10. Post-incident review written to Failure Memory and an Incident record regardless of
    root cause.

## Credential rotation & compromised-agent revocation

- Full credential rotation (all vault-issued secrets, all connector tokens) is a
  documented, drillable procedure, not just theoretically possible — used both for
  scheduled hygiene and as an incident-response action.
- A compromised-agent revocation path exists independent of full DR: Security Guardian
  or owner can revoke a specific agent/workflow's credentials and freeze it without
  requiring a full-system recovery, keeping the common case (one bad agent) cheap to
  contain.

## Provider-outage / model-provider fallback

Covered in `docs/architecture/07-model-routing.md#fallback-chain--degraded-operation` —
treated as a DR concern for the *capability* layer, distinct from data-loss DR.

## Local degraded operation

If the private cloud/control-plane environment is unreachable but owner-local hardware
and the local model tier are available, GREEN-tier read/monitoring functions continue
against the most recent locally-cached World Model state (explicitly marked stale),
while all AMBER/RED execution halts until full connectivity and integrity are restored.
