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

	"gridkeep/control-api/internal/modules/agents"
	"gridkeep/control-api/internal/modules/artefacts"
	"gridkeep/control-api/internal/modules/auditlog"
	"gridkeep/control-api/internal/modules/capacityoffers"
	"gridkeep/control-api/internal/modules/deployments"
	"gridkeep/control-api/internal/modules/identity"
	"gridkeep/control-api/internal/modules/images"
	"gridkeep/control-api/internal/modules/models"
	"gridkeep/control-api/internal/modules/operators"
	"gridkeep/control-api/internal/modules/placement"
	"gridkeep/control-api/internal/modules/platformadmin"
	"gridkeep/control-api/internal/modules/policies"
	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/modules/registry"
	"gridkeep/control-api/internal/modules/subscriptions"
	"gridkeep/control-api/internal/modules/tenancy"
	"gridkeep/control-api/internal/modules/workloads"
	"gridkeep/control-api/internal/platform/cache"
	"gridkeep/control-api/internal/platform/config"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/mailer"
	"gridkeep/control-api/internal/platform/pki"
	"gridkeep/control-api/internal/platform/policyengine"
	"gridkeep/control-api/internal/platform/secretsvault"
	"gridkeep/control-api/internal/platform/security"
)

// Deps are the already-constructed external connections the app is built
// from. Cache may be nil (subscriptions/entitlements fall back to reading
// Postgres directly -- see subscriptions.Service). CA is loaded (or
// generated on first use) by the caller before NewRouter runs, since doing
// so requires a database round trip -- see pki.LoadOrCreate. Storage is
// typed as artefacts.ObjectStore (an interface, not the concrete
// *storage.Client) specifically so integration tests can substitute an
// in-memory fake instead of requiring a live MinIO instance.
type Deps struct {
	Store           *dbpkg.Store
	Cache           *cache.Client
	Logger          *slog.Logger
	Config          *config.Config
	MFAKey          []byte
	CA              *pki.CA
	Storage         artefacts.ObjectStore
	SecretsVaultKey []byte
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

	agentsSvc := agents.NewService(d.Store, d.CA, agents.Config{
		BootstrapTokenTTL: d.Config.AgentBootstrapTokenTTL,
		CertificateTTL:    d.Config.AgentCertificateTTL,
	})
	agentsHandlers := agents.NewHandlers(agentsSvc, d.Logger)

	policyEngineClient := policyengine.NewClient(d.Config.PolicyEngineURL, d.Config.PolicyEngineTimeout)
	policiesSvc := policies.NewService(d.Store, policyEngineClient, policies.Config{
		PolicyEngineTimeout: d.Config.PolicyEngineTimeout,
	})
	policiesHandlers := policies.NewHandlers(policiesSvc, d.Logger)

	modelsSvc := models.NewService(d.Store)
	modelsHandlers := models.NewHandlers(modelsSvc, d.Logger)

	imagesSvc := images.NewService(d.Store)
	imagesHandlers := images.NewHandlers(imagesSvc, d.Logger)

	artefactsSvc := artefacts.NewService(d.Store, d.Storage, artefacts.Config{
		MaxContentLength: d.Config.ArtefactMaxContentLength,
		UploadURLTTL:     d.Config.ArtefactUploadURLTTL,
		DownloadURLTTL:   d.Config.ArtefactDownloadURLTTL,
	})
	artefactsHandlers := artefacts.NewHandlers(artefactsSvc, d.Logger)

	workloadsSvc := workloads.NewService(d.Store)
	workloadsHandlers := workloads.NewHandlers(workloadsSvc, d.Logger)

	capacityOffersSvc := capacityoffers.NewService(d.Store)
	capacityOffersHandlers := capacityoffers.NewHandlers(capacityOffersSvc, d.Logger)

	placementSvc := placement.NewService(d.Store, policyEngineClient)
	placementHandlers := placement.NewHandlers(placementSvc, d.Logger)

	secretsVault, err := secretsvault.New(d.SecretsVaultKey)
	if err != nil {
		panic(err) // SecretsVaultKey is validated by the caller before reaching here.
	}
	deploymentsSvc := deployments.NewService(d.Store, d.CA, secretsVault)
	deploymentsHandlers := deployments.NewHandlers(deploymentsSvc, d.Logger)

	validator := identity.SessionValidatorAdapter{Service: identitySvc}
	// These two routes authenticate a machine identity (a bootstrap token,
	// or a request signature made with an issued certificate's private
	// key) rather than a session cookie, so CSRF's double-submit-cookie
	// check does not apply to them -- see httpserver.CSRFProtect.
	csrfExemptPrefixes := []string{"/api/v1/agent-bootstrap", "/api/v1/agents/", "/api/v1/cluster-agent-bootstrap", "/api/v1/cluster-agents/"}
	router := httpserver.NewRouter(d.Logger, d.Config.CORSAllowedOrigins, d.Config.SessionCookieSecure, validator, d.Config.SessionCookieName, csrfExemptPrefixes)

	identity.Mount(router, identityHandlers, d.Logger)
	tenancy.MountTopLevel(router, tenancyHandlers)
	operators.MountTopLevel(router, operatorsHandlers)
	registry.MountTopLevel(router, registryHandlers, authz)
	agents.MountMachineFacing(router, agentsHandlers)
	deployments.MountMachineFacing(router, deploymentsHandlers)

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
		policies.MountTenantScoped(r, policiesHandlers, authz)
		models.MountTenantScoped(r, modelsHandlers, authz)
		images.MountTenantScoped(r, imagesHandlers, authz)
		artefacts.MountTenantScoped(r, artefactsHandlers, authz)
		workloads.MountTenantScoped(r, workloadsHandlers, authz)
		placement.MountTenantScoped(r, placementHandlers, authz)
		deployments.MountTenantScoped(r, deploymentsHandlers, authz)
	})

	router.Route("/api/v1/operators/{operatorID}", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		operators.MountOperatorScoped(r, operatorsHandlers, authz)
		subscriptions.MountOperatorScoped(r, subsHandlers, authz)
		auditlog.MountOperatorScoped(r, auditHandlers, authz)
		registry.MountOperatorScoped(r, registryHandlers, authz)
		agents.MountOperatorScoped(r, agentsHandlers, authz)
		capacityoffers.MountOperatorScoped(r, capacityOffersHandlers, authz)
		deployments.MountOperatorScoped(r, deploymentsHandlers, authz)
	})

	platformadmin.Mount(router, platformHandlers, auditHandlers, authz, func(r chi.Router) {
		images.MountPlatformScoped(r, imagesHandlers, authz)
	})

	return router
}
