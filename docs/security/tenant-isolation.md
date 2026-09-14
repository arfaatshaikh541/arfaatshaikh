# Tenant isolation and administrative separation

Tenant context is derived from the authenticated user and an active membership. An `X-Organisation-ID` header selects a tenant but never grants access by itself. Every tenant-scoped endpoint resolves membership server-side and checks explicit permission codes.

Platform administrators are stored separately from organisation memberships. They receive no implicit tenant access. Read-only support access requires a specific, unexpired, non-revoked grant tied to one organisation and is auditable. Future write-capable break-glass access must use a separate approval flow and is outside Unit 4.

Audit and security events are append-only application records: their models intentionally omit `updated_at`. Database-level immutability enforcement and PostgreSQL RLS policies will be added during the final Milestone 1 hardening unit, after live PostgreSQL integration testing is available.
