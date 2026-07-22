package identity

import (
	"log/slog"

	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/platform/httpserver"
)

// Mount registers identity routes onto r. Public routes (register, login,
// verify-email, password-reset) require no session. Account routes require
// an authenticated session via httpserver.RequireAuth.
func Mount(r chi.Router, h *Handlers, logger *slog.Logger) {
	r.Route("/api/v1/auth", func(r chi.Router) {
		r.Post("/register", h.Register)
		r.Post("/verify-email", h.VerifyEmail)
		r.Post("/login", h.Login)
		r.Post("/mfa/verify", h.VerifyMFA)
		r.Post("/password-reset/request", h.RequestPasswordReset)
		r.Post("/password-reset/confirm", h.ResetPassword)

		r.Group(func(r chi.Router) {
			r.Use(httpserver.RequireAuth())
			r.Post("/logout", h.Logout)
			r.Get("/me", h.Me)
			r.Post("/change-password", h.ChangePassword)
			r.Post("/step-up", h.StepUp)
			r.Post("/mfa/enroll", h.EnrollMFA)
			r.Post("/mfa/confirm", h.ConfirmMFA)
			r.Post("/mfa/disable", h.DisableMFA)
		})
	})
}
