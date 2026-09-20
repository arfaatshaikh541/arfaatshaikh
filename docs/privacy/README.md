# Privacy Architecture

## Principles

LOCAL-FIRST, PRIVATE-FIRST, ZERO-PUBLIC-ACCESS, MINIMUM-DATA-EXPOSURE. Privacy is treated
as a security control, not a preference — because AURA operates real businesses with real
customer and financial data, and it is a single point of aggregation for all of it.

## Model Privacy Gateway

Every piece of context that could leave the private boundary (i.e., go to a hosted
frontier model API) passes through the Gateway first:

```
Raw context → Data Classifier → Secret Detector → PII Detector →
Context Minimizer → Redaction/Tokenization → Provider Policy Check →
Audit Log → (send to selected provider) or (route to local model instead)
```

- **Data Classifier**: tags context by sensitivity class (public, internal, confidential,
  restricted — e.g., restricted = financial account numbers, health info, credentials,
  legal privilege material).
- **Secret Detector**: regex + entropy + known-pattern scanning for API keys, tokens,
  passwords before any external call; hard-blocks the call if detected, does not just warn.
- **PII Detector**: identifies personal data categories (names, emails, government IDs,
  financial identifiers) so minimization and jurisdictional rules can apply.
- **Context Minimizer**: sends only the fields the specific task needs, not the entire
  record (e.g., a copywriting task gets brand voice guidelines, not the customer's full
  CRM history).
- **Redaction/Tokenization**: replaces restricted values with stable tokens where the
  task doesn't need the real value (e.g., "CUSTOMER_A" instead of a real name for a
  drafting task); de-tokenized only at the final trusted step if truly required.
- **Provider Policy Check**: enforces per-provider rules (e.g., "restricted-class data
  never leaves local inference," "confidential-class data only to providers with a
  zero-retention agreement").
- **Local-model fallback**: if a task involves restricted-class data and no compliant
  provider is configured, the task routes to the local/private model tier or is held for
  owner decision — it does not silently downgrade to a non-compliant provider.

## What we explicitly do NOT run

No analytics SDKs, no advertising SDKs, no unnecessary telemetry, no tracking of AURA's
customers beyond what each business function legitimately needs (e.g., CRM naturally
holds customer data — that's business data, not owner surveillance). No training of
external providers' models on owner/business data — this must be contractually and
technically enforced (zero-retention / no-training API tiers only) and independently
verified in `docs/security/supply-chain.md` vendor review.

## Encryption & storage posture

| Data class | At rest | In transit | Notes |
|---|---|---|---|
| Restricted (credentials, financial, health, legal) | Encrypted, customer-managed keys, HSM/KMS-backed | mTLS only | Local inference only |
| Confidential (customer PII, contracts, internal strategy) | Encrypted (KMS-backed) | mTLS/TLS 1.3 | Zero-retention provider APIs only, minimized context |
| Internal (drafts, metrics, ops data) | Encrypted | TLS 1.3 | Standard provider routing allowed |
| Public (published content, marketing copy already live) | Standard | TLS 1.3 | No restriction |

All of: databases, object storage, vector store, and backups are encrypted at rest.
Backups are additionally encrypted with a separate key held offline (see
`docs/disaster-recovery/README.md`).

## Local vs. private-endpoint vs. hosted inference

- **Local inference** (on owner-controlled hardware): used for restricted-class data,
  and as the offline-degraded-mode fallback. Trade-off: weaker capability than frontier
  hosted models, and requires the owner to provision capable hardware
  (`architecture/14-deployment-and-infrastructure.md#hardware`).
- **Private inference endpoints** (VPC-isolated hosted deployment of a frontier model,
  where available, with contractual no-training/no-retention terms): used for
  confidential-class data needing frontier capability.
- **Standard hosted APIs** (with zero-retention business terms): used for internal/public
  class data and lower-sensitivity tasks, chosen for cost/capability/latency.

## Confidential computing & hardware-backed keys

Where the deployment target supports it (TEE/SEV-SNP/TDX on cloud, or Secure
Enclave/TPM on owner hardware), the Credential Broker's signing keys and the memory
encryption keys are hardware-backed and never exist in plaintext outside the enclave.
This is an aspirational upgrade path, not assumed for Milestone 0 — see roadmap.

## Egress control

Network egress filtering (`docs/security/network.md`) is itself a privacy control:
agents cannot exfiltrate data to arbitrary destinations even if an injection attack
convinces them to try, because the destination isn't on the allowlist.
