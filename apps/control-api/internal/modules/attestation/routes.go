package attestation

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountOperatorScoped registers onto a router already nested under
// /api/v1/operators/{operatorID} by app.go.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorMembership()).Get("/attestation-policies", h.ListPolicies)
	r.With(authz.RequireOperatorPermission("operator.attestation.manage")).Post("/attestation-policies", h.CreatePolicy)
	r.With(authz.RequireOperatorPermission("operator.attestation.manage")).Post("/attestation-policies/{policyID}/revoke", h.RevokePolicy)

	r.With(authz.RequireOperatorMembership()).Get("/cluster-agents/{clusterAgentID}/attestation-results", h.ListOperatorResults)
}

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("attestation.view")).Get("/deployments/{deploymentID}/attestation-results", h.ListTenantResults)
}

// MountMachineFacing registers the two routes a cluster agent itself calls
// to run the remote-attestation protocol: neither carries a user session,
// mirroring Milestone 6/7's MountMachineFacing for the same reason (an
// agent is not a user). Both are certificate-signature authenticated,
// verified inside the service, not by any session middleware.
func MountMachineFacing(r chi.Router, h *Handlers) {
	r.Post("/api/v1/cluster-agents/{clusterAgentID}/attestation-sessions", h.RequestSession)
	r.Post("/api/v1/cluster-agents/{clusterAgentID}/attestation-sessions/{sessionID}/evidence", h.SubmitEvidence)
}
