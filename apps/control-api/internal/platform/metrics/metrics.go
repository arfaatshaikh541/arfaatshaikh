// Package metrics exposes Prometheus instrumentation for control-api's own
// operational health -- request rate, latency, and status-code
// distribution -- distinct from the customer-facing SLO/incident feature
// Milestone 10 built for tenants' and operators' own workloads/
// infrastructure. Served on a separate port from application traffic (see
// cmd/server/main.go), the same "internal-only, network-policy-restricted"
// posture a real deployment should give any metrics endpoint, mirroring the
// worker module's own separate health port.
package metrics

import (
	"net/http"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	httpRequestsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "control_api_http_requests_total",
		Help: "Total HTTP requests, labeled by method, route pattern, and status code.",
	}, []string{"method", "route", "status"})

	httpRequestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "control_api_http_request_duration_seconds",
		Help:    "HTTP request latency in seconds, labeled by method and route pattern.",
		Buckets: prometheus.DefBuckets,
	}, []string{"method", "route"})
)

// Observe records one completed request's outcome. Called with the
// route *pattern* (e.g. "/api/v1/enterprises/{tenantID}"), never the raw
// URL path -- recording by pattern keeps label cardinality bounded
// regardless of how many distinct tenant/resource IDs appear in real
// traffic; recording every raw path would let cardinality grow without
// bound as new tenants/resources are created; Prometheus has no
// affordance for that.
func Observe(method, routePattern string, status int, duration time.Duration) {
	statusLabel := strconv.Itoa(status)
	httpRequestsTotal.WithLabelValues(method, routePattern, statusLabel).Inc()
	httpRequestDuration.WithLabelValues(method, routePattern).Observe(duration.Seconds())
}

// Handler returns the /metrics endpoint's http.Handler (Prometheus
// exposition format), meant to be served on its own port -- see
// cmd/server/main.go -- not mounted onto the public API router.
func Handler() http.Handler {
	return promhttp.Handler()
}
