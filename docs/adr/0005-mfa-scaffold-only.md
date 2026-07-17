# ADR-0005: MFA architecture scaffolded, enrollment deferred

## Status
Accepted (Milestone 1 approval item #7).

## Decision
`User.mfa_enabled` and `Session.assurance_level` columns exist from
Milestone 1's first migration so the step-up-authentication dependency
chain has somewhere to read from later without a schema migration
blocking that work. Actual TOTP enrollment, verification, and any
step-up-required gating on sensitive actions (billing changes, role
changes) are not implemented in Milestone 1.

## Consequences
- `mfa_enabled` is always `false` today; no user can enable MFA yet.
- No endpoint currently checks `assurance_level`.
- This is a known limitation, not a bug: MFA enrollment is explicitly
  out of scope for Milestone 1 per the approved plan.
