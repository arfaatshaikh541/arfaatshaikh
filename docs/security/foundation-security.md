# Foundation security controls

- Non-root users execute application containers.
- Secrets are environment supplied and excluded from version control.
- Configuration fails at startup when the application secret is too short.
- PostgreSQL and Redis are not published to the host network.
- MinIO buckets remain private.
- CORS uses an explicit origin list and explicit methods and headers.
- The frontend removes the framework disclosure header and establishes CSP, referrer, permissions and content-type protections.
- Readiness fails closed when a required dependency cannot be verified.

Authentication, CSRF, RBAC and tenant isolation belong to later Milestone 1 units and are not claimed by this unit.
