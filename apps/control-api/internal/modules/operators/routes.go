package operators

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/httpserver"
)

// MountTopLevel registers routes not nested under {operatorID} and not
// collliding with another module's top-level routes. Invitation acceptance
// uses a distinct path from the enterprise equivalent
// (/api/v1/operator-invitations/accept vs /api/v1/invitations/accept)
// because an invitation token alone does not indicate which scope it
// belongs to. The shared /api/v1/me group is registered once by main.go --
// see MountMeRoutes.
func MountTopLevel(r chi.Router, h *Handlers) {
	r.Route("/api/v1/operators", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		r.Post("/", h.CreateOperator)
	})

	r.Route("/api/v1/operator-invitations", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		r.Post("/accept", h.AcceptInvitation)
	})
}

// MountMeRoutes registers onto the shared /api/v1/me router main.go
// constructs once.
func MountMeRoutes(r chi.Router, h *Handlers) {
	r.Get("/operator-memberships", h.ListMyMemberships)
}

// MountOperatorScoped registers routes onto a router already nested under
// /api/v1/operators/{operatorID} by main.go. main.go applies
// httpserver.RequireAuth() once for the whole nested group before calling
// any *Scoped mount function -- it must not be repeated here (chi panics if
// Use() is called after routes already exist on the router).
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorMembership()).Get("/", h.GetOperator)
	r.With(authz.RequireOperatorPermission("operator.profile.manage")).Patch("/", h.UpdateOperator)
	r.With(authz.RequireOperatorMembership()).Get("/members", h.ListMembers)
	r.With(authz.RequireOperatorPermission("operator.profile.manage")).Post("/invitations", h.CreateInvitation)
}
