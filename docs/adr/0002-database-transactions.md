# ADR 0002: Asynchronous database and explicit transaction boundaries

## Status

Accepted.

## Decision

Use SQLAlchemy 2 asynchronous sessions with asyncpg. Maintain one process-level engine and one
session factory. Request dependencies roll back after exceptions. Multi-write business operations
use an explicit unit-of-work boundary.

## Consequences

Connection pooling is stable, commits are not hidden inside repositories, and later tenant-context
and row-level-security controls can be applied at transaction start. Integration tests will use a
real PostgreSQL service rather than SQLite because PostgreSQL behaviour is part of the product's
security model.
