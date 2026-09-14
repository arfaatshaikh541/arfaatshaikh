# Milestone 11 Unit 1: Developer Platform Foundation

This unit establishes a governed integration surface for first-party, partner, and future public applications.

## Security boundaries

- API secrets are represented only by hashes after issuance.
- Credentials receive explicit allowlisted scopes and bounded rate limits.
- Suspended or revoked applications cannot receive usable credentials.
- Webhooks require public HTTPS endpoints and reject loopback, private, link-local, reserved, and local hostnames.
- Webhook deliveries are idempotent per subscription and event.
- Payload signatures use HMAC-SHA256 over `timestamp.payload`.
- Retry decisions are deterministic, bounded to twelve attempts, and limited to transient failures.

## Portable acceptance

Unit tests validate schema registration, scope governance, endpoint safety, signature verification, and retry policy. Live DNS resolution, outbound delivery, queue execution, and secret-manager integration remain deployment validations.
