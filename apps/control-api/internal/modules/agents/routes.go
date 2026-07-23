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

	r.With(authz.RequireOperatorMembership()).Get("/cluster-agents", h.ListClusterAgents)
	r.With(authz.RequireOperatorPermission("operator.agents.manage")).Post("/cluster-agents", h.RegisterClusterAgent)
	r.With(authz.RequireOperatorMembership()).Get("/cluster-agents/{clusterAgentID}/certificates", h.ListClusterAgentCertificates)
	r.With(authz.RequireOperatorPermission("operator.agents.manage")).Post("/cluster-agents/{clusterAgentID}/revoke", h.RevokeClusterAgent)
	r.With(authz.RequireOperatorMembership()).Get("/cluster-agents/{clusterAgentID}/control-messages", h.ListControlMessages)
	r.With(authz.RequireOperatorMembership()).Get("/cluster-agents/{clusterAgentID}/deployment-plan-validations", h.ListDeploymentPlanValidations)

	r.With(authz.RequireOperatorPermission("operator.agents.manage")).Post("/deployment-plan-requests", h.RequestDeploymentPlanValidation)
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
	r.Post("/api/v1/agents/{agentID}/rotate-certificate", h.RotateOperatorAgentCertificate)

	r.Post("/api/v1/cluster-agent-bootstrap", h.ClusterAgentBootstrap)
	r.Post("/api/v1/cluster-agents/{clusterAgentID}/rotate-certificate", h.RotateClusterAgentCertificate)
	r.Get("/api/v1/cluster-agents/{clusterAgentID}/control-messages/pending", h.PollPendingControlMessages)
	r.Post("/api/v1/cluster-agents/{clusterAgentID}/control-messages/{messageID}/respond", h.RespondToControlMessage)

	// Public: any interested party (an agent that has never yet
	// established a session-equivalent identity, or anyone else) may fetch
	// the CA's own certificate -- it is inherently public information, the
	// same way a TLS server's certificate is.
	r.Get("/api/v1/platform-ca/certificate", h.PlatformCACertificate)
}
