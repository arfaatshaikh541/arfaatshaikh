# Private Deployment Topology, Sandboxing & Network Diagram

## Deployment topology

```
Owner Device (passkey / hardware key / TPM-Secure Enclave)
      |  WireGuard (Tailscale/Headscale) — mTLS session
Secure Access Layer  (private network edge; no public ingress)
      |
Private Control Plane
   - Owner auth & session
   - Policy Engine (OPA) admin API   [owner-write only]
   - Approval Engine UI/API
   - Credential Broker admin (grant/revoke) [owner-write only]
   - Observability dashboards (read)
      |  mTLS, service identities, network segmentation
Private Agent Runtime
   - Executive Intelligence service
   - Durable workflow engine (Temporal)
   - Agent sandboxes (per-task, gVisor/Firecracker)
   - Security Guardian  [separate trust boundary — see below]
      |  mTLS, scoped short-lived credentials only
Private Data Plane
   - World Model (Postgres + pgvector)
   - Object storage (MinIO / encrypted cloud storage)
   - Credential Vault (HashiCorp Vault)
   - Audit log (hash-chained, Guardian holds independent copy)
      |  allowlisted egress only, DNS-monitored
External Connectors  (email, CRM, ad platforms, GitHub, banking read APIs, etc.)
```

## Security Guardian's separate trust boundary

Drawn deliberately outside the "Private Agent Runtime" box above in terms of *trust*,
even though it may be co-located operationally: it has its own service identity, its own
credential root (issued directly by the Credential Broker's owner-controlled bootstrap,
not derivable by the EI), its own write path to the audit log, and the sole write path
to the Action Broker's freeze flag. The EI has no API that reaches Security Guardian's
configuration or an ability to instruct it.

## Network segmentation rules (illustrative allowlist matrix)

| From \ To | Control Plane | Agent Runtime | Data Plane | External |
|---|---|---|---|---|
| Owner Device | ✅ (mTLS+passkey) | ❌ direct | ❌ direct | ❌ |
| Control Plane | — | ✅ (issue tasks/policy) | ✅ (policy/audit read) | ❌ |
| Agent Runtime | ✅ (status/approval requests) | — | ✅ (scoped, per-task) | ✅ (allowlisted per task only) |
| Data Plane | ✅ (audit/query) | ✅ (scoped reads/writes via World Model API) | — | ❌ |
| Security Guardian | ✅ (alerts) | ✅ (freeze command, read-only monitoring) | ✅ (independent audit read) | ❌ |

No cell above is "implicitly allow" — every path is an explicit, reviewed firewall/
service-mesh rule. This table itself is versioned policy-as-code, not a diagram that can
drift from reality.

## Sandbox lifecycle (per task)

```
Task claimed by workflow → orchestrator requests sandbox
  → minimal image selected (per capability family, immutable, no baked secrets)
  → network policy attached (per connector manifest's declared egress needs only)
  → Credential Broker issues scoped token(s) for this task, injected at runtime
  → agent executes, bounded by timeout
  → sandbox destroyed (ephemeral) regardless of success/failure
  → credentials auto-revoked on destroy (belt-and-suspenders beyond TTL expiry)
```

## Why this matters for "isolation of compromise"

Each box above is a genuine trust boundary, not a logical grouping for documentation
purposes: crossing a boundary requires going through mTLS-authenticated, policy-checked
service calls. A compromised agent sandbox can, at worst, misuse the specific short-lived
scoped credential it was issued for its one task — it cannot reach the vault's master
keys, cannot reach the Policy Engine's write API, cannot reach Security Guardian's
config, and cannot reach another agent's task context, because none of those paths exist
for it to abuse in the first place.
