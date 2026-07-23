// Package app wires every module's service and HTTP handlers into a single
// chi.Mux. It exists as its own package (rather than living inline in
// cmd/server/main.go) so integration tests can build the exact same router
// production traffic goes through, against a real test database, via
// httptest -- instead of re-implementing the wiring or testing modules in
// isolation from the authorization pipeline that actually protects them.
package app

import (
	"log/slog"
	"time"

	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/auditlog"
	"gridkeep/control-api/internal/modules/identity"
	"gridkeep/control-api/internal/modules/operators"
	"gridkeep/control-api/internal/modules/platformadmin"
	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/modules/registry"
	"gridkeep/control-api/internal/modules/subscriptions"
	"gridkeep/control-api/internal/modules/tenancy"
	"gridkeep/control-api/internal/platform/cache"
	"gridkeep/control-api/internal/platform/config"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/mailer"
	"gridkeep/control-api/internal/platform/security"
)

// Deps are the already-constructed external connections the app is built
// from. Cache may be nil (subscriptions/entitlements fall back to reading
// Postgres directly -- see subscriptions.Service).
type Deps struct {
	Store  *dbpkg.Store
	Cache  *cache.Client
	Logger *slog.Logger
	Config *config.Config
	MFAKey []byte
}

// NewRouter builds the fully-wired control-api HTTP router.
func NewRouter(d Deps) *chi.Mux {
	hasher := security.NewPasswordHasher(d.Config.Argon2Memory, d.Config.Argon2Iterations, d.Config.Argon2Parallelism)
	totpManager, err := security.NewTOTPManager(d.MFAKey, "GRIDKEEP")
	if err != nil {
		panic(err) // MFAKey is validated by the caller before reaching here.
	}
	mail := mailer.New(d.Config.SMTPHost, d.Config.SMTPPort, d.Config.SMTPFrom)

	identitySvc := identity.NewService(d.Store, hasher, totpManager, mail, identity.Config{
		SessionTTL:            d.Config.SessionTTL,
		StepUpTTL:             d.Config.StepUpTTL,
		EmailVerificationTTL:  d.Config.EmailVerificationTTL,
		PasswordResetTTL:      d.Config.PasswordResetTTL,
		MFAChallengeTTL:       5 * time.Minute,
		MFAMaxAttempts:        d.Config.MFAMaxAttempts,
		LoginLockoutThreshold: d.Config.LoginLockoutThreshold,
		LoginLockoutWindow:    d.Config.LoginLockoutWindow,
		PublicBaseURL:         d.Config.CORSAllowedOrigins[0],
	})
	identityHandlers := identity.NewHandlers(identitySvc, d.Logger, d.Config.SessionCookieName, d.Config.SessionCookieSecure)

	authz := rbac.NewMiddleware(d.Store, d.Logger)

	tenancySvc := tenancy.NewService(d.Store, mail, tenancy.Config{
		InvitationTTL: 7 * 24 * time.Hour,
		PublicBaseURL: d.Config.CORSAllowedOrigins[0],
	})
	tenancyHandlers := tenancy.NewHandlers(tenancySvc, d.Logger)

	operatorsSvc := operators.NewService(d.Store, mail, operators.Config{
		InvitationTTL: 7 * 24 * time.Hour,
		PublicBaseURL: d.Config.CORSAllowedOrigins[0],
	})
	operatorsHandlers := operators.NewHandlers(operatorsSvc, d.Logger)

	subsSvc := subscriptions.NewService(d.Store, d.Cache)
	subsHandlers := subscriptions.NewHandlers(subsSvc, d.Logger)

	auditSvc := auditlog.NewService(d.Store)
	auditHandlers := auditlog.NewHandlers(auditSvc, d.Logger)

	platformSvc := platformadmin.NewService(d.Store)
	platformHandlers := platformadmin.NewHandlers(platformSvc, subsSvc, d.Logger)

	registrySvc := registry.NewService(d.Store)
	registryHandlers := registry.NewHandlers(registrySvc, d.Logger)

	validator := identity.SessionValidatorAdapter{Service: identitySvc}
	router := httpserver.NewRouter(d.Logger, d.Config.CORSAllowedOrigins, d.Config.SessionCookieSecure, validator, d.Config.SessionCookieName)

	identity.Mount(router, identityHandlers, d.Logger)
	tenancy.MountTopLevel(router, tenancyHandlers)
	operators.MountTopLevel(router, operatorsHandlers)
	registry.MountTopLevel(router, registryHandlers, authz)

	router.Route("/api/v1/me", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		tenancy.MountMeRoutes(r, tenancyHandlers)
		operators.MountMeRoutes(r, operatorsHandlers)
	})

	router.Route("/api/v1/enterprises/{tenantID}", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		tenancy.MountTenantScoped(r, tenancyHandlers, authz)
		subscriptions.MountEnterpriseScoped(r, subsHandlers, authz)
		auditlog.MountEnterpriseScoped(r, auditHandlers, authz)
	})

	router.Route("/api/v1/operators/{operatorID}", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		operators.MountOperatorScoped(r, operatorsHandlers, authz)
		subscriptions.MountOperatorScoped(r, subsHandlers, authz)
		auditlog.MountOperatorScoped(r, auditHandlers, authz)
		registry.MountOperatorScoped(r, registryHandlers, authz)
	})

	platformadmin.Mount(router, platformHandlers, auditHandlers, authz)

	return router
}
