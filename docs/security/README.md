# Security Architecture

Cross-references: Security Guardian and Credential Broker are specified in
`docs/architecture/04-agent-architecture.md`; the threat model and top-50 failure
scenarios are in `docs/threat-model/`. This document covers the remaining structural
security controls.

## Sandboxing architecture

Every agent executes inside an isolated sandbox scoped to its task:

- **Container-per-task** (not container-per-agent-role) for ephemeral agents — a fresh,
  minimal, immutable image per task, destroyed on completion. No image is reused across
  tasks with different sensitivity levels.
- **Filesystem**: no host filesystem access beyond explicitly declared, task-scoped
  mounts (e.g., a code-review task gets a read-only checkout of the relevant repo, not
  the whole disk).
- **Network**: default-deny; only the specific egress destinations the task's connector
  scope requires are allowlisted (see Network Security below).
- **Syscall restriction**: seccomp/gVisor-class isolation where the runtime supports it,
  to reduce kernel attack surface from a compromised dependency inside the sandbox.
- **No credential material baked into images** — credentials are injected at runtime by
  the Credential Broker, scoped and short-lived, per the Action Broker flow.
- **Code-execution tasks** (agents writing/running code) run in a further-isolated
  execution sandbox distinct from the orchestration sandbox, since it's the highest-risk
  surface for sandbox escape attempts.

## Network security

- **Deny-by-default ingress**: no agent, connector, or control-plane service accepts
  unsolicited inbound connections from the public internet. The only internet-facing
  surface is the Secure Access Layer (owner's private networking).
- **Controlled, allowlisted egress**: per-task, per-connector destination allowlists.
  An agent handling email cannot suddenly open a connection to an arbitrary domain
  because the model "decided to" — the sandbox's network policy blocks it at the
  network layer regardless of what the model outputs.
- **DNS monitoring**: DNS queries logged and checked against the allowlist; unexpected
  domains trigger Security Guardian alerts even if the connection itself was blocked
  (an attempted exfiltration is itself a signal).
- **mTLS internally**: every service-to-service call (EI ↔ Action Broker ↔ Policy
  Engine ↔ Credential Broker ↔ connectors) is mutually authenticated, not just
  encrypted.
- **Service identities**: each service has its own workload identity (SPIFFE/SPIRE-style
  or cloud-native workload identity), so "which service made this call" is a
  cryptographic fact, not a log claim.
- **Network segmentation**: control plane, agent runtime, data plane, and vault are on
  separate network segments with explicit, minimal allowed paths between them (see
  `docs/architecture/09-sandboxing-and-network.md` for the diagram).
- **Rate limiting**: per-agent and per-connector, to bound the damage of a runaway loop
  or a compromised credential being used for bulk exfiltration.
- **Outbound data-loss controls**: large or unusual outbound payloads (e.g., a sudden
  export of the full customer table) require explicit policy allowance; the Model
  Privacy Gateway and Action Broker both inspect payload shape, not just destination.

## Credential vault (detail)

Secrets never live in: prompts, chat history, source code, agent memory, git, logs, or
the vector database. Enforced by:

- Vault technology: HashiCorp Vault (self-hosted, private-first) or cloud KMS/HSM,
  chosen per deployment (see ADR in `docs/adr/`); OS secure enclave/keychain used for the
  owner's own device-bound keys.
- **Workload identity → short-lived token exchange**: an agent never receives a static
  API key. The Credential Broker exchanges the agent's ephemeral workload identity +
  an approved Action Broker request for a token scoped to exactly that action, with a
  TTL measured in minutes, not days.
- **Static long-lived secrets** (e.g., a connector's OAuth refresh token) are held only
  by the Credential Broker itself, never distributed to agents; the Broker performs the
  actual external call's authentication step on the agent's behalf where the connector
  protocol allows it (broker-mediated calls), or issues a narrowly scoped short-lived
  access token where it doesn't.
- **Secret-scanning** runs on every commit, every log sink, and every memory write path
  as a defense-in-depth backstop, not the primary control.

## Supply-chain security

- Dependency pinning + lockfiles for every service; no floating version ranges in
  production builds.
- SBOM generated per build/release.
- Signed artifacts and (where practical) reproducible builds, verified before deploy.
- Automated vulnerability scanning (dependencies + containers) gating CI.
- Secret scanning and SAST gating CI.
- Dependency review required for any new dependency (who maintains it, install-time
  scripts, permissions requested) before it's approved for use — especially for MCP
  servers and tool integrations, which are effectively granted tool-calling trust.
- Minimal base images (distroless/scratch where feasible).
- Provenance attestations (SLSA-style) for build artifacts.
- Branch protection + required review on the AURA repository itself; no direct pushes
  to the deploy branch.
- Signed releases.

## Prompt-injection defense

Full detail in `docs/security/prompt-injection.md`. Summary: content provenance
labeling separates OWNER COMMANDS / SYSTEM POLICIES / TRUSTED BUSINESS RULES from
EXTERNAL DATA at ingestion; external data is never eligible to trigger an action above
GREEN without an independent, policy-defined confirmation step; tool-call arguments
derived from external content are validated against expected schema/value ranges before
execution; output is checked for injected instructions being echoed back before it's
used to justify a subsequent action.

## Audit architecture

Every consequential action records: agent identity, model + model version, task, the
initiating goal, the policy decision (and why), input provenance, tools used,
credentials requested (scope + TTL, not the secret value), external actions taken,
money involved, approval record (who/when/what was shown), result, errors, and rollback
information.

- **Tamper-evident**: hash-chained append-only log (each entry includes the hash of the
  previous entry); a break in the chain is itself detectable and alerting.
- **Independent custody**: the Security Guardian holds its own copy of the audit stream,
  written via a path the EI/agents cannot write to, so a compromised EI cannot rewrite
  history to hide an incident.
- **Queryable**: the "show me the evidence" and "why did you make that decision" owner
  commands are implemented as queries over this store joined with Decision Memory, not
  as a fresh LLM explanation generated after the fact.

## Failure containment summary

Compromise of one agent → bounded by: sandbox isolation, per-task scoped credentials, no
shared long-lived secrets, network segmentation. Compromise of an agent must not reach:
another agent (no shared state beyond the World Model's access-controlled API), the EI
(separate service, separate trust boundary), the Credential Vault (agents never hold
vault master keys), the owner account (owner auth is hardware-backed and never delegated
to an agent), or the host (sandbox isolation + minimal image + no host mount).
