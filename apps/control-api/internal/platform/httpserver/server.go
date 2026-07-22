package httpserver

import (
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
)

// NewRouter builds the base router with global middleware. Modules mount
// their own route groups onto the returned router in main.go.
func NewRouter(logger *slog.Logger, allowedOrigins []string, cookieSecure bool, validator SessionValidator, cookieName string) *chi.Mux {
	r := chi.NewRouter()

	r.Use(chimw.RequestID)
	// Deliberately not using chi's RealIP middleware: it unconditionally
	// trusts X-Forwarded-For / X-Real-IP / True-Client-IP, letting any client
	// spoof the IP address recorded in login_attempts and session/audit
	// evidence (GHSA-3fxj-6jh8-hvhx). r.RemoteAddr is the actual TCP peer and
	// cannot be spoofed. When this API is deployed behind a trusted reverse
	// proxy, replace this with a resolver that only trusts those headers
	// from known proxy IPs.
	r.Use(requestLogger(logger))
	r.Use(chimw.Recoverer)
	r.Use(chimw.Timeout(30 * time.Second))
	r.Use(SecurityHeaders)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   allowedOrigins,
		AllowedMethods:   []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Content-Type", "X-CSRF-Token"},
		AllowCredentials: true,
		MaxAge:           300,
	}))
	r.Use(WithOptionalSession(validator, cookieName))
	r.Use(CSRFProtect(cookieSecure))

	r.Get("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})

	return r
}

func requestLogger(logger *slog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			ww := chimw.NewWrapResponseWriter(w, r.ProtoMajor)
			next.ServeHTTP(ww, r)
			logger.InfoContext(r.Context(), "http_request",
				"method", r.Method,
				"path", r.URL.Path,
				"status", ww.Status(),
				"duration_ms", time.Since(start).Milliseconds(),
				"request_id", chimw.GetReqID(r.Context()),
			)
		})
	}
}
