# Milestone 10 Unit 2: Operations and Resilience

This unit adds governed operational alert rules, alert events, incident records, runbook execution evidence, and fail-closed resilience evaluation.

## Boundaries

- Alert rules may reference only metrics the application contract declares as emitted.
- High and critical alerts require valid runbooks.
- SEV1/SEV2 incidents require command and communications readiness.
- SEV1 requires a verified rollback path.
- Production resilience fails while a SEV1 or SEV2 incident remains open.
- This unit defines application contracts; live monitoring backends and paging integrations remain deployment verification work.
