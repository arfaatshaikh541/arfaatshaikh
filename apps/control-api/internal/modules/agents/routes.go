package agents

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountOperatorScoped registers onto a router already nested under
// /api/v1/operators/{operatorID} by app.go, alongside other modules'
// operator-scoped routes. Every route here is session-authenticated.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorMembership()).Get("/agents", h.ListAgents)
	r.With(authz.RequireOperatorPermission("operator.agents.manage")).Post("/agents", h.RegisterAgent)
	r.With(authz.RequireOperatorMembership()).Get("/agents/{agentID}/certificates", h.ListAgentCertificates)
	r.With(authz.RequireOperatorPermission("operator.agents.manage")).Post("/agents/{agentID}/revoke", h.RevokeAgent)

	r.With(authz.RequireOperatorMembership()).Get("/capacity-snapshots", h.ListCapacitySnapshots)
}

// MountMachineFacing registers the two routes an operator-agent itself
// calls: neither carries a user session, since an agent is not a user.
// Bootstrap is authenticated by the one-time bootstrap token; capacity
// snapshot submission is authenticated by an ECDSA signature made with the
// agent's issued certificate's private key (see Service.SubmitCapacitySnapshot
// for why this deliberately does not go through the same session-scoped
// RLS path every other route in this codebase uses).
func MountMachineFacing(r chi.Router, h *Handlers) {
	r.Post("/api/v1/agent-bootstrap", h.Bootstrap)
	r.Post("/api/v1/agents/{agentID}/capacity-snapshots", h.SubmitCapacitySnapshot)
}
