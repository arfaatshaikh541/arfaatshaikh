# Milestone 11 Unit 2 — API Access, Usage Metering, and Auditability

This unit adds deterministic API authorization policy, tenant-bound scope enforcement, quota evaluation, idempotent usage records, and tamper-evident developer audit events.

## Security boundaries

- An active application and active non-expired credential are required.
- The credential organisation must match the request tenant.
- Required scopes are allowlisted and must be explicitly granted.
- Quota exhaustion fails closed with a 429 policy result.
- Usage records require canonical route templates and idempotency keys.
- Audit evidence stores SHA-256 fingerprints, not raw secrets or client IP addresses.

## Deployment limitations

Distributed counters, live authentication middleware, persistent request metering, and production billing remain unverified until Redis/PostgreSQL and deployment integration are exercised.
