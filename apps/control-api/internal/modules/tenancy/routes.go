package tenancy

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/httpserver"
)

// MountTopLevel registers routes that are not nested under a {tenantID}
// path segment and do not collide with another module's top-level routes
// (POST /api/v1/enterprises, POST /api/v1/invitations/accept). The shared
// /api/v1/me group is registered once by main.go -- see MountMeRoutes.
func MountTopLevel(r chi.Router, h *Handlers) {
	r.Route("/api/v1/enterprises", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		r.Post("/", h.CreateTenant)
	})

	r.Route("/api/v1/invitations", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		r.Post("/accept", h.AcceptInvitation)
	})
}

// MountMeRoutes registers onto the shared /api/v1/me router main.go
// constructs once (since both tenancy and operators contribute routes under
// it, and chi panics on a second r.Route() call for the same path).
func MountMeRoutes(r chi.Router, h *Handlers) {
	r.Get("/enterprise-memberships", h.ListMyMemberships)
}

// MountTenantScoped registers routes onto a router already nested under
// /api/v1/enterprises/{tenantID} by main.go, alongside other modules'
// tenant-scoped routes (subscriptions, audit) sharing the same {tenantID}
// path segment. main.go applies httpserver.RequireAuth() once for the whole
// nested group before calling any *Scoped mount function -- chi panics if
// Use() is called again after routes have already been registered on the
// same router, so it must not be repeated here.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterpriseMembership()).Get("/", h.GetTenant)
	r.With(authz.RequireEnterprisePermission("settings.manage")).Patch("/", h.UpdateTenant)
	r.With(authz.RequireEnterprisePermission("settings.manage")).Patch("/sustainability-preferences", h.UpdateSustainabilityPreferences)
	r.With(authz.RequireEnterpriseMembership()).Get("/members", h.ListMembers)
	r.With(authz.RequireEnterprisePermission("users.manage")).Post("/invitations", h.CreateInvitation)
}
