package platformadmin

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/auditlog"
	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/httpserver"
)

// Mount registers all platform-administration routes under /api/v1/platform.
// Every route requires a platform_role_assignments-granted permission --
// enterprise/operator memberships grant nothing here. extraMounters are
// called with the same sub-router (e.g. images.MountPlatformScoped) --
// chi panics if two separate top-level Route() calls both claim
// "/api/v1/platform", so every platform-scoped module's routes must be
// registered inside this single Route block rather than mounting a second
// one elsewhere.
func Mount(r chi.Router, h *Handlers, auditHandlers *auditlog.Handlers, authz *rbac.Middleware, extraMounters ...func(chi.Router)) {
	r.Route("/api/v1/platform", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())

		r.With(authz.RequirePlatformPermission("platform.tenants.manage")).Get("/enterprises", h.ListTenants)
		r.With(authz.RequirePlatformPermission("platform.tenants.manage")).Patch("/enterprises/{tenantID}/status", h.SetTenantStatus)
		r.With(authz.RequirePlatformPermission("platform.billing.manage")).Patch("/enterprises/{tenantID}/subscription", h.AssignEnterprisePlan)

		r.With(authz.RequirePlatformPermission("platform.operators.manage")).Get("/operators", h.ListOperators)
		r.With(authz.RequirePlatformPermission("platform.operators.manage")).Patch("/operators/{operatorID}/status", h.SetOperatorStatus)
		r.With(authz.RequirePlatformPermission("platform.operators.manage")).Patch("/operators/{operatorID}/trust-level", h.SetOperatorTrustLevel)
		r.With(authz.RequirePlatformPermission("platform.billing.manage")).Patch("/operators/{operatorID}/subscription", h.AssignOperatorPlan)

		r.With(authz.RequirePlatformPermission("platform.support_access.grant")).Post("/support-access-grants", h.RequestSupportAccessGrant)
		r.With(authz.RequirePlatformPermission("platform.support_access.grant")).Post("/support-access-grants/{grantID}/approve", h.ApproveSupportAccessGrant)
		r.With(authz.RequirePlatformPermission("platform.support_access.grant")).Post("/support-access-grants/{grantID}/revoke", h.RevokeSupportAccessGrant)
		r.With(authz.RequirePlatformPermission("platform.support_access.view")).Get("/support-access-grants", h.ListSupportAccessGrants)

		auditlog.MountPlatformScoped(r, auditHandlers, authz)

		for _, mount := range extraMounters {
			mount(r)
		}
	})
}
