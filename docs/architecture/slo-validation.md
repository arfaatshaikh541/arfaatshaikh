# SLO Validation

This document defines Service Level Objectives for **control-api itself, as a running service** —
distinct from, and not to be confused with, the customer-facing SLO feature Milestone 10 built
(`internal/modules/assurance`'s `slo_definitions`/`slo_evaluations`), which lets *tenants and
operators* define SLOs for *their own* workloads and infrastructure. This document is about GRIDKEEP
monitoring its own control plane's health, using the Prometheus metrics
`docs/architecture/observability.md` describes.

## Why these targets, and how they were derived

Every target below is grounded in either a real measurement taken this milestone
(`docs/testing/performance-and-load-testing.md`) or a widely-used industry-standard baseline for a
service of this shape (a stateless API backed by Postgres). None is a guess presented as validated
production data — the difference is called out explicitly per objective.

## SLOs

### Availability: 99.9% of requests succeed (non-5xx) over a rolling 30-day window

**Basis**: industry-standard baseline for a service without a formally negotiated, higher-tier SLA;
not independently measured this milestone (a 30-day rolling window cannot be validated from a single
development-container test run). **Validation query** (once deployed with real traffic):

```promql
1 - (
  sum(rate(control_api_http_requests_total{status=~"5.."}[30d]))
  /
  sum(rate(control_api_http_requests_total[30d]))
)
```

**What this milestone's chaos-testing drill (`docs/testing/chaos-testing.md`) already confirms
qualitatively**: a real Postgres outage produces clean `500`s (correctly countable toward an
error-budget calculation using the query above), not connection hangs or silent request drops that
would corrupt this metric — so the metric itself is trustworthy once real traffic exists to compute
it from.

### Latency: p99 < 200ms for authenticated read requests, p99 < 1s for the login endpoint specifically

**Basis**: **directly measured** this milestone (`docs/testing/performance-and-load-testing.md`):
an authenticated database-backed read (`GET /api/v1/auth/me`) measured p99 33-49ms in this sandbox,
comfortably under a 200ms target with headroom for slower production-hardware/network conditions;
the Argon2id-bound login path measured p99 687ms, comfortably under a 1-second target but with much
less headroom — consistent with `docs/testing/performance-and-load-testing.md`'s own capacity-planning
note that login is this service's real bottleneck. **The login endpoint deliberately gets its own,
looser target** rather than being held to the same 200ms bar as every other endpoint, because Argon2id's
cost is the intended security property, not a defect to optimize away.

**Validation query** (once deployed):

```promql
histogram_quantile(0.99,
  sum(rate(control_api_http_request_duration_seconds_bucket{route="/api/v1/auth/login"}[5m])) by (le)
)
```

(swap the `route` label for any other endpoint to validate its own latency SLO against the 200ms
general target).

### Error rate: < 0.1% of requests return 5xx over a rolling 5-minute window (the error-budget "burn rate" signal, distinct from the 30-day availability SLO above)

**Basis**: industry-standard baseline (a fast-burning-error-budget alert threshold, meant to fire long
before the 30-day availability SLO itself would be breached, giving an operator time to react).
**Validation query**:

```promql
sum(rate(control_api_http_requests_total{status=~"5.."}[5m]))
/
sum(rate(control_api_http_requests_total[5m]))
> 0.001
```

## What still needs real production traffic to validate

Every PromQL query above is written and ready to run the moment this service has real traffic to
compute over — but **none of these targets have been validated against sustained, real-world traffic
patterns**, only against this milestone's own short, sandbox-scale load-test and chaos-test runs.
This is the same honest limitation `docs/testing/performance-and-load-testing.md` already states for
its own raw throughput numbers: directionally trustworthy (the *shape* of the data — login is the
slow path, reads are fast, outages fail cleanly — is architectural and will hold on real hardware),
but the specific percentile thresholds above should be revisited against the first month of real
production metrics, not treated as permanently fixed the moment this document is written.

## Relationship to the customer-facing SLO feature

It would be architecturally tempting to store control-api's own SLOs in the same
`slo_definitions`/`slo_evaluations` tables Milestone 10 built — but those tables are explicitly
scoped to a `enterprise_tenant_id` or `operator_id` (RLS-enforced, per
`docs/security/tenant-isolation-audit.md`'s inventory), because they represent a *tenant's or
operator's own* commitment about *their own* resources. Control-api's own operational SLOs have no
tenant or operator owner — they describe the platform itself, to the platform's own operators, not a
tenant-facing or operator-facing product feature. Reusing those tables would require either a fake
"platform" tenant/operator row (an ugly modeling hack) or weakening the RLS boundary those tables
correctly enforce. This document, and the Prometheus metrics it queries, are the deliberately
separate mechanism for a deliberately separate concern.
