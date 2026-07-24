# Observability

This document covers control-api's **own** operational observability — the logs and metrics an
operator of GRIDKEEP itself would use to monitor the control plane. It is distinct from, and should
not be confused with, the customer-facing SLO/incident/alert feature Milestone 10 built
(`internal/modules/assurance`) — that feature lets *tenants and operators* define and monitor SLOs
for *their own* workloads and infrastructure; this document is about monitoring GRIDKEEP's control
plane itself.

## Structured logging (existing since Milestone 1)

`internal/platform/logging` provides a JSON `slog` logger (`INFO` in production, `DEBUG` in
development). Every request is logged by `requestLogger`
(`internal/platform/httpserver/server.go`) with method, path, status, duration, and request ID — all
correlatable via chi's `RequestID` middleware, which every log line and every downstream audit-event
write can reference. `logging`'s own package doc states the governing rule: handlers must never log
secrets, passwords, tokens, or full request/response bodies — confirmed with zero violations across
the entire codebase in `docs/security/application-security-audit.md`'s secrets-handling review.

## Metrics (new this milestone)

`internal/platform/metrics` adds Prometheus instrumentation, exposed on its own port
(`CONTROL_API_METRICS_PORT`, default `9090`) — **deliberately never mounted onto the public API
router**. A real deployment should restrict this port to the in-cluster Prometheus scraper via
network policy (see `infrastructure/helm`'s NetworkPolicy notes), never expose it through the same
ingress/load balancer as application traffic, the same reasoning `WORKER_HEALTH_PORT` already
established for the worker service's own separate health port.

Two metrics, both labeled by HTTP method and **route pattern** (e.g.
`/api/v1/enterprises/{tenantID}`, never the raw path with a real tenant UUID in it — this keeps
label cardinality bounded regardless of how many tenants/resources exist in production):

- `control_api_http_requests_total{method, route, status}` — a counter, the basis for both
  request-rate and error-rate dashboards/alerts.
- `control_api_http_request_duration_seconds{method, route}` — a histogram (Prometheus default
  buckets), the basis for latency percentile dashboards/alerts (the same p50/p90/p99 shape
  `docs/testing/performance-and-load-testing.md`'s manual `hey` runs measured by hand this
  milestone — in production, Prometheus computes these continuously from every real request instead).

Recorded in `requestLogger` itself (`internal/platform/httpserver/server.go`), right after the
existing structured-log line, using chi's `RouteContext(r.Context()).RoutePattern()` to get the
matched route pattern (falling back to `"unmatched"` for a request no route ever matched, e.g. a
404) — one middleware, one place, covering every mounted route automatically as new ones are added,
with no per-route instrumentation code required anywhere else in the codebase.

Verified with a real test (`internal/platform/metrics/metrics_test.go`): records a sample
observation, serves it through the real `promhttp.Handler()`, and asserts the exposition-format
output contains the expected counter and histogram lines with the expected labels — not just that
the code compiles.

## What is not yet built

- **Distributed tracing** (OpenTelemetry spans across control-api → policy-engine, or across
  control-api → a real Kubernetes cluster once one is integrated) does not exist. The request-ID
  correlation described above gives a poor-man's version of this within a single service's logs, but
  there is no trace propagation across the policy-engine HTTP call or any other outbound call this
  service makes. A future milestone wanting real distributed tracing should add OpenTelemetry SDK
  instrumentation to the outbound HTTP clients (`internal/platform/policyengine`, `internal/platform/storage`)
  and propagate a trace context header, not build a bespoke correlation mechanism.
- **Business-level metrics** (e.g. "reservations created per minute," "placement evaluations by
  decision outcome") are not yet instrumented — only the generic HTTP request/latency/status metrics
  above exist. These would be straightforward additions (a handful of `promauto.NewCounterVec` calls
  in the relevant service methods, following the exact pattern this milestone established) once a
  specific dashboard/alert need identifies which business events matter most to track.
- **Log aggregation/shipping** (to a real log backend — Loki, Elasticsearch, CloudWatch, whichever a
  real deployment chooses) is not this codebase's concern; it emits structured JSON to stdout, and
  shipping stdout to a real backend is a deployment/infrastructure decision (typically a DaemonSet or
  sidecar in a real Kubernetes deployment), not something the application itself should own.

## Verdict

Structured logging was already sound before this milestone. Metrics were entirely absent before
this milestone and are now present, tested, and correctly separated (by port) from application
traffic — a real, working observability foundation, not a stub. Tracing and business-level metrics
are honestly documented as not yet built, with a clear, low-effort path for a future milestone that
needs them.
