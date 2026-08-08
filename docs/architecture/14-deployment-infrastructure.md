# Deployment Strategy, Hardware, Cloud vs. Local, Operating Costs

## Deployment strategy

Milestone-gated (see `docs/roadmap.md`), never a big-bang launch:

1. Single-node private deployment (owner-controlled hardware or a private VPC) running
   the full stack at small scale — appropriate through early milestones.
2. Staging environment mirrors production topology at smaller resource allocation;
   every capability is proven in staging (with synthetic/sandboxed data) before its
   autonomy level is raised in production.
3. Blue/green or canary rollout for the AURA platform's own updates (not customer-facing
   product features — AURA updating itself is a DevOps Engineer / Build Engine task
   subject to the same CI/CD gates as anything else, per `05-capability-engines.md`).
4. Infrastructure-as-code (Terraform/Pulumi) for everything — no manually-clicked
   infrastructure, so disaster recovery (`docs/disaster-recovery/README.md`) can
   actually rebuild from scratch.

## Cloud vs. local/private infrastructure analysis

| Dimension | Local/owner hardware | Private cloud (VPC, customer-managed keys) |
|---|---|---|
| Privacy | Strongest — data never leaves owner's physical control | Strong if configured correctly, but trusts cloud provider's infra + legal compulsion risk |
| Capability | Limited by owner's hardware budget for inference | Access to more powerful managed services, elastic scale |
| Reliability | Owner is the single point of failure for power/network/hardware | Provider SLAs, but introduces provider-outage dependency |
| Cost model | High upfront (hardware), low marginal | Low upfront, ongoing usage-based cost, can spike |
| Operational burden | Owner (or a hired ops contractor) maintains physical infra | Provider maintains infra; owner maintains config |
| Recommendation | Use for: local reasoning/embedding model tier, vault unseal material, backup copies | Use for: control plane + agent runtime + data plane, in a private VPC with no public ingress, customer-managed KMS keys |

**Recommended default**: hybrid. Core services run in a private cloud VPC (predictable
ops burden, strong isolation primitives, better DR story for a single owner without
dedicated IT staff), while local inference hardware handles the most sensitive
workloads and serves as the offline-degraded-mode fallback. This is a recommendation to
validate with the owner during Milestone 0 planning, not a foreclosed decision — the
"local-first" preference in the brief is honored for the *sensitive-data* tier
specifically, while accepting that a single owner realistically cannot out-operate a
major cloud provider's physical security and uptime for the base platform.

## Hardware recommendations (if/when local inference is provisioned)

- A single workstation/server with a modern consumer-to-prosumer GPU (24GB+ VRAM class)
  is sufficient for the local reasoning-model and embedding-model tiers at single-owner
  task volume; this is a starting point, not a hard spec, and should be sized against
  the actual open-weight model chosen in the Model Router's local tier.
- Redundant power (UPS) and a wired network connection if this machine is load-bearing
  for degraded-mode operation.
- TPM 2.0 present and used for local key sealing.
- This hardware is explicitly **not** required for Milestone 0 — Milestone 0 can run
  local-tier workloads on a modest CPU-only fallback or defer the local tier entirely and
  rely on private-cloud/zero-retention-API routing with the Privacy Gateway's
  restricted-class rule simply meaning "hold for owner decision" until local inference
  exists.

## Estimated operating-cost categories (categories, not fabricated numbers)

Actual figures depend entirely on task volume, chosen providers, and deployment shape —
providing specific AED/USD figures now would be a fabricated estimate. Categories to
budget and track from Milestone 0 onward, each with its own line in the Financial
Control budget envelopes:

- Frontier model API usage (highest-variance cost driver; tracked per capability class)
- Cloud infrastructure (compute, storage, network egress) for the private VPC deployment
- Local inference hardware amortization (if provisioned)
- Connector/SaaS subscription costs (CRM, email platform, ad platforms' own fees,
  accounting software, etc. — these are the owner's business tool costs, not AURA-
  specific, but AURA's spend recommendations touch them)
- Secrets/observability tooling if using managed variants instead of self-hosted
- Backup storage (redundant, offsite/immutable snapshots)
- Optional: paid security tooling (managed SAST/dependency-scanning tiers) if the
  open-source defaults prove insufficient at scale

AURA's own Financial Analyst role should track actual spend against these categories
from day one, feeding the Weekly Board Report's financial-performance section — meaning
AURA's own operating cost is itself Business Memory data, not an unmeasured externality.
