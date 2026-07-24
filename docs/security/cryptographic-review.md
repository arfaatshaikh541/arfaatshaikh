# Cryptographic Review

**Scope:** every cryptographic primitive in `apps/control-api` — PKI/certificate authority,
envelope encryption for workload secrets, attestation, machine-caller signature verification, random
number generation, and TLS configuration. **Method:** exhaustive, file-by-file review; every claim
cites a real `file:line`.

## PKI / Certificate Authority (`internal/platform/pki`) — sound

- **ECDSA P-256** for both the CA and every issued leaf certificate (`ca.go:104`, `agent.go:28`) —
  a modern, appropriately-sized curve, not RSA. `verify.go` type-asserts every certificate's public
  key to `*ecdsa.PublicKey`, so a non-ECDSA key could never even be verified by this codebase.
- **Signature algorithm**: ECDSA-SHA256 throughout (Go's `x509.CreateCertificate` selects this
  automatically from an ECDSA key; message-level signatures explicitly hash with SHA-256 before
  `ecdsa.SignASN1`). No MD5/SHA1 anywhere in this package.
- **CA private key**: encrypted at rest with AES-256-GCM before being persisted, protected by a
  required, no-fallback `PKI_CA_ENCRYPTION_KEY` (32-byte, base64) — the server refuses to start
  without a valid one.
- **Validity periods**: CA root 10 years (with a 5-minute backdated `NotBefore` for clock-skew
  tolerance); leaf/agent certificates default to 72 hours (`AGENT_CERTIFICATE_TTL_HOURS`,
  environment-configurable), a sensibly short-lived operational credential.
- **Serial numbers**: randomly generated 128-bit values via `crypto/rand` for both the CA and every
  leaf certificate — not sequential or predictable.
- No weak default found anywhere: no MD5/SHA1 signing path, no never-expiring certificate path,
  32-byte minimum key length enforced.

## secretsvault (`internal/platform/secretsvault`) — sound, with one architecturally-acknowledged simplification

- AES-256-GCM, fresh random nonce (via `crypto/rand`) generated per encryption call, prepended to
  the ciphertext — no nonce-reuse path exists anywhere.
- **This is a single-key model, not full DEK/KEK envelope wrapping** — the package's own doc comment
  explicitly states this is a deliberate stand-in for a future Vault transit-engine implementation
  ("Vault holds exactly one key with exactly one job"). This is not a defect; it's an honestly
  documented simplification appropriate for a mock/local-development vault, with the real key coming
  from a required, no-fallback `SECRETS_VAULT_ENCRYPTION_KEY` — the same fail-closed posture as the
  PKI CA key. A future milestone integrating real Vault should replace this module wholesale, not
  patch around it.
- No hardcoded key or IV found anywhere, including in the test file (test-only keys are never shared
  with any production code path).

## Attestation (`internal/platform/attestation`) — sound trust-boundary placement

- The mock provider itself does no cryptographic evidence-format parsing (by design — its own doc
  comment states this plainly) and is purely an expected-vs-reported measurement comparison. **The
  real cryptographic trust boundary is one layer up**, in `internal/modules/attestation/service.go`:
  every session-request and evidence-submission call is gated by the same ECDSA/SHA-256 signature
  verification (`pki.VerifySignature`) used everywhere else in this codebase, checked against the
  calling agent's current certificate before any attestation-specific logic runs.
- Replay protection is real: the attestation nonce is always server-minted via `crypto/rand` (never
  agent-chosen), a signed request must fall within a bounded time window, and a session/nonce is
  atomically consumed on first successful evidence submission — a second submission against the same
  session is rejected, not silently re-processed.

## Machine-caller signature verification — one consistent, correct primitive everywhere

Every machine-caller code path this codebase has (agent bootstrap/rotation, control-message
signing, deployment-plan responses, attestation, billing usage reports, network-provisioning
results, container-image signatures) calls the identical `pki.VerifySignature` —
ECDSA-P256/SHA-256 via `ecdsa.VerifyASN1`. This is a genuine strength: there is exactly one signature
primitive in this codebase, used consistently, rather than several ad-hoc implementations that could
each independently get something subtly wrong. `ecdsa.VerifyASN1` verifies a public-key signature (no
secret value is compared byte-for-byte), so the usual HMAC-style constant-time-comparison concern
does not apply here — no substitute `==`/`bytes.Equal` comparison was found standing in for it
anywhere, which is what would have been the actual finding had one existed.

## Random number generation — clean

**Zero occurrences of `math/rand` anywhere in this repository.** Every security-relevant random
value in this codebase — CA/leaf key generation, certificate serial numbers, AES-GCM nonces/IVs,
attestation and deployment nonces, opaque session/reset/verification tokens — uses `crypto/rand`
exclusively. This is a genuinely clean result across the entire codebase, not a sampled subset.

## Finding (Informational): no explicit TLS configuration anywhere

- No `tls.Config`, `MinVersion`, or `CipherSuites` literal exists anywhere in `apps/control-api`.
  The HTTP server itself (`cmd/server/main.go`) never terminates TLS — implying TLS termination, if
  any, happens at an upstream reverse proxy/load balancer, consistent with this being a
  containerized service meant to sit behind one (see `docs/deployment/production-deployment.md`).
  This is architecturally reasonable (TLS termination is a deployment/infrastructure concern, not
  something a stateless application process typically owns), but worth stating explicitly: **this
  codebase has no opinion of its own about minimum TLS version or cipher suite** — whichever layer
  terminates TLS in a real deployment must be configured deliberately (TLS 1.2 minimum, modern
  cipher suites), since nothing here enforces or documents a requirement.
- Outbound clients (the MinIO/S3 client, the policy-engine HTTP client) similarly set no explicit
  TLS configuration of their own, relying on Go's stdlib default `http.Transport` — a reasonable
  default (Go's stdlib TLS defaults are modern and safe), but again worth noting as "inherited
  default," not "explicitly chosen and reviewed."
- The mailer (`internal/platform/mailer`) sends plaintext SMTP with no STARTTLS — explicitly
  documented in its own doc comment as targeting a local Mailpit dev-capture service only, not a
  finding against a real deployment's mail relay (which this codebase does not itself configure).

## Verdict

No cryptographic weakness was found in any primitive choice, key size, or randomness source in this
codebase. Every signature and encryption operation uses a modern, appropriately-sized algorithm via
`crypto/rand`-sourced randomness, consistently, everywhere. The one architectural simplification
(secretsvault's single-key model) is honestly documented as a placeholder for a real Vault
integration, not presented as more than it is. The one informational gap (no explicit TLS
configuration anywhere in this codebase) reflects a deliberate "TLS termination is an infrastructure
concern" architecture rather than an oversight, but should be explicitly documented and configured at
whichever layer owns TLS termination in a real deployment.
