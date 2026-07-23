# ADR 0007: Local Development Certificate Authority for Operator-Agent Identity

## Status
Accepted (Milestone 2)

## Context
The approved architecture (§14-15) specifies certificate-based identity for operator-agents
and cluster-agents: "GRIDKEEP operates (or delegates to Vault PKI) a private CA issuing
operator-agent and cluster-agent certificates," with enrollment via a bootstrap token → CSR →
short-lived certificate flow. Milestone 1 already deferred real Vault integration to
architecture-only (`docs/adr/0003-session-and-mfa-model.md` notes SSO/WebAuthn/Vault-backed
integrations are scaffolded, not live). Milestone 2 needs real, working certificate issuance
now, since "operator agent registration" and "certificate lifecycle" are both in its scope.

## Decision
`internal/platform/pki` implements a real X.509 certificate authority using Go's standard
`crypto/x509`/`crypto/ecdsa` packages — not a stub, not a mock. On first use it generates an
ECDSA P-256 root key pair and a long-lived (10-year) self-signed root certificate, then
persists both durably in a new singleton `platform_ca` table, with the private key
AES-256-GCM-encrypted at rest under `PKI_CA_ENCRYPTION_KEY` — the exact same
required-with-no-insecure-fallback pattern already used for `MFA_ENCRYPTION_KEY`. Every
subsequent server start loads the same CA rather than generating a new one, so previously
issued agent certificates remain valid.

Certificate issuance (`CA.SignCSR`) validates the CSR's self-signature (proof the requester
holds the corresponding private key) and then builds the leaf certificate's Subject entirely
from a value the caller supplies out-of-band — never from anything the CSR itself claims. In
practice this means `agents.Service.Bootstrap` passes the `operator_agent.id` it already
resolved from a validated, single-use bootstrap token, so a malicious CSR claiming to be a
different agent is simply ignored, not trusted (see working rule #19: never trust a
client-supplied identity claim).

Signature verification (`pki.VerifySignature`) is a standalone function taking a certificate
PEM, a message, and a signature — used by `agents.Service.SubmitCapacitySnapshot` to check
that a capacity-snapshot submission was actually signed by the private key matching the
submitting agent's current, unrevoked, unexpired certificate.

## Alternatives considered
- **Defer certificate issuance entirely, ship only the registration data model.** Rejected:
  Milestone 2's scope explicitly includes "certificate lifecycle," and working rule #6
  ("do not use pseudocode in accepted implementation work") rules out a stub that always
  returns a fake certificate.
- **Real Vault PKI integration now.** Rejected for the same reason Vault integration was
  deferred in Milestone 1: it requires a live Vault deployment this environment cannot
  runtime-validate (see `docs/operations/local-development.md`'s Docker Hub limitation), and
  building against an unverifiable integration would violate working rule #9 ("do not claim
  an integration works against real infrastructure unless it was tested against real
  infrastructure").
- **True mTLS at the HTTP transport layer.** Rejected for Milestone 2: control-api itself
  never terminates TLS anywhere in this architecture (§43, production deployment terminates
  TLS at the ingress/load balancer) — wiring client-certificate verification into the Go
  `net/http` server would contradict that existing, deliberate separation. Instead,
  capacity-snapshot submissions are authenticated by an **application-level** ECDSA signature
  over the request body, checked against the certificate's public key — transport-agnostic,
  consistent with how sessions/tokens/audit hash-chains are all real, verifiable,
  application-level cryptography rather than relying on the transport layer.

## Consequences
- A real, working PKI exists today; the only thing that differs from the target production
  architecture is *who operates the root of trust* (a locally-generated key vs. a
  Vault-issued intermediate CA) — swapping the backing store for `LoadOrCreate` is the whole
  migration path when Vault integration lands for real.
- Certificates are ECDSA P-256 with a configurable TTL (`AGENT_CERTIFICATE_TTL_HOURS`,
  default 72h, matching the architecture's 24-72h guidance) and `ExtKeyUsageClientAuth` only
  — they are not suitable for, and are not used for, server-side TLS termination anywhere.
- Revocation is application-level (`agent_certificates.revoked_at`, checked by
  `currentValidCertificatePEM` before every signature verification) rather than
  CRL/OCSP-based, since there is no TLS terminator in this architecture to consult a
  revocation list at the connection level — see §15's note that revocation includes "an
  application-level 'agent trust status' check on every signed message," which is exactly
  what this implements.
- `platform_ca` is deliberately excluded from the test suite's per-test truncation list
  (`internal/testutil/testutil.go`) — like `roles`/`permissions`, it is durable
  infrastructure the whole test run shares, not per-test state.
