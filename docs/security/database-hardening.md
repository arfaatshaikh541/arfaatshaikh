# Database hardening

Milestone 1 uses PostgreSQL row-level security as defence in depth. Request-scoped user and organisation identifiers are written with transaction-local `set_config` calls. Policies protect tenant-scoped roles, memberships, support grants, audit events and security events.

Application permission checks remain mandatory. RLS is not treated as a replacement for service-layer authorisation.

Audit and security event tables are append-only through database triggers. Corrections must be represented by new events rather than mutation of history.
