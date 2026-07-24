package metrics_test

import (
	"io"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"gridkeep/control-api/internal/platform/metrics"
)

func TestObserveExposesPrometheusMetrics(t *testing.T) {
	metrics.Observe("GET", "/api/v1/enterprises/{tenantID}", 200, 42*time.Millisecond)

	req := httptest.NewRequest("GET", "/metrics", nil)
	rec := httptest.NewRecorder()
	metrics.Handler().ServeHTTP(rec, req)

	if rec.Code != 200 {
		t.Fatalf("expected /metrics to return 200, got %d", rec.Code)
	}
	body, err := io.ReadAll(rec.Body)
	if err != nil {
		t.Fatalf("read metrics body: %v", err)
	}
	text := string(body)

	if !strings.Contains(text, `control_api_http_requests_total{method="GET",route="/api/v1/enterprises/{tenantID}",status="200"}`) {
		t.Fatalf("expected control_api_http_requests_total counter with the observed labels, got:\n%s", text)
	}
	if !strings.Contains(text, `control_api_http_request_duration_seconds_bucket{method="GET",route="/api/v1/enterprises/{tenantID}"`) {
		t.Fatalf("expected control_api_http_request_duration_seconds histogram buckets with the observed labels, got:\n%s", text)
	}
}
