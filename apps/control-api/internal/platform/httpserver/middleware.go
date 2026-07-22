package httpserver

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"net/http"

	"github.com/google/uuid"
)

// SessionValidator is implemented by the identity module and injected here
// so the platform HTTP layer never imports a domain module directly.
type SessionValidator interface {
	ValidateSession(ctx context.Context, rawSessionToken string) (AuthenticatedUser, error)
}

const csrfCookieName = "gridkeep_csrf"
const csrfHeaderName = "X-CSRF-Token"

// SecurityHeaders sets baseline defensive HTTP response headers.
func SecurityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "same-origin")
		w.Header().Set("Cache-Control", "no-store")
		next.ServeHTTP(w, r)
	})
}

// WithOptionalSession resolves the caller's session (if a valid session
// cookie is present) and attaches it to the request context. It never
// rejects the request — routes that require authentication must additionally
// use RequireAuth.
func WithOptionalSession(validator SessionValidator, cookieName string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			cookie, err := r.Cookie(cookieName)
			if err != nil || cookie.Value == "" {
				next.ServeHTTP(w, r)
				return
			}
			user, err := validator.ValidateSession(r.Context(), cookie.Value)
			if err != nil {
				next.ServeHTTP(w, r)
				return
			}
			ctx := withAuthUser(r.Context(), user)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// RequireAuth rejects the request with 401 UNAUTHENTICATED if no valid
// session was resolved by WithOptionalSession.
func RequireAuth() func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if _, ok := AuthUser(r.Context()); !ok {
				writeUnauthenticated(w)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

func writeUnauthenticated(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_, _ = w.Write([]byte(`{"error":{"code":"UNAUTHENTICATED","message":"Authentication is required."}}`))
}

// CSRFProtect implements double-submit-cookie CSRF protection: a
// non-HttpOnly cookie carries a random token the frontend must echo back in
// the X-CSRF-Token header on every state-changing request. GET/HEAD/OPTIONS
// are exempt because they must not mutate state.
func CSRFProtect(cookieSecure bool) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			existing, err := r.Cookie(csrfCookieName)
			token := ""
			if err == nil {
				token = existing.Value
			}
			if token == "" {
				token = generateCSRFToken()
				http.SetCookie(w, &http.Cookie{
					Name:     csrfCookieName,
					Value:    token,
					Path:     "/",
					HttpOnly: false,
					Secure:   cookieSecure,
					SameSite: http.SameSiteLaxMode,
				})
			}

			if r.Method == http.MethodGet || r.Method == http.MethodHead || r.Method == http.MethodOptions {
				next.ServeHTTP(w, r)
				return
			}

			header := r.Header.Get(csrfHeaderName)
			if header == "" || token == "" || header != token {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusForbidden)
				_, _ = w.Write([]byte(`{"error":{"code":"FORBIDDEN","message":"CSRF token missing or invalid."}}`))
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

func generateCSRFToken() string {
	buf := make([]byte, 32)
	_, _ = rand.Read(buf)
	return base64.RawURLEncoding.EncodeToString(buf)
}

// NewRequestID generates a request-scoped correlation ID for structured
// logging and tracing.
func NewRequestID() string {
	return uuid.New().String()
}
