package deployments

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("workloads.deploy")).Post("/deployments", h.CreateDeployment)
	r.With(authz.RequireEnterprisePermission("deployments.view")).Get("/deployments", h.ListDeployments)
	r.With(authz.RequireEnterprisePermission("deployments.view")).Get("/deployments/{deploymentID}", h.GetDeployment)
	r.With(authz.RequireEnterprisePermission("deployments.view")).Get("/deployments/{deploymentID}/events", h.ListDeploymentEvents)

	r.With(authz.RequireEnterprisePermission("workloads.deploy")).Post("/deployments/{deploymentID}/plans", h.CreatePlan)
	r.With(authz.RequireEnterprisePermission("deployments.view")).Get("/deployments/{deploymentID}/plans", h.ListPlans)
	r.With(authz.RequireEnterprisePermission("workloads.deploy")).Post("/deployments/{deploymentID}/plans/{planID}/request-approval", h.RequestPlanApproval)
	r.With(authz.RequireEnterprisePermission("deployments.approve")).Post("/deployments/{deploymentID}/plans/{planID}/approve", h.ApprovePlan)
	r.With(authz.RequireEnterprisePermission("deployments.approve")).Post("/deployments/{deploymentID}/plans/{planID}/reject", h.RejectPlan)
	r.With(authz.RequireEnterprisePermission("workloads.deploy")).Post("/deployments/{deploymentID}/plans/{planID}/submit", h.SubmitPlan)

	r.With(authz.RequireEnterprisePermission("workloads.scale")).Post("/deployments/{deploymentID}/scale", h.Scale)
	r.With(authz.RequireEnterprisePermission("workloads.pause")).Post("/deployments/{deploymentID}/pause", h.Pause)
	r.With(authz.RequireEnterprisePermission("workloads.pause")).Post("/deployments/{deploymentID}/resume", h.Resume)
	r.With(authz.RequireEnterprisePermission("workloads.terminate")).Post("/deployments/{deploymentID}/terminate", h.Terminate)
	r.With(authz.RequireEnterprisePermission("deployments.rollback")).Post("/deployments/{deploymentID}/rollback", h.Rollback)
	r.With(authz.RequireEnterprisePermission("workloads.retry")).Post("/deployments/{deploymentID}/retry", h.Retry)

	r.With(authz.RequireEnterprisePermission("credentials.manage")).Post("/workload-versions/{versionID}/secrets", h.CreateWorkloadSecret)
	r.With(authz.RequireEnterprisePermission("credentials.manage")).Get("/workload-versions/{versionID}/secrets", h.ListWorkloadSecrets)
	r.With(authz.RequireEnterprisePermission("credentials.manage")).Delete("/workload-versions/{versionID}/secrets/{secretID}", h.DeleteWorkloadSecret)
}

// MountOperatorScoped registers onto a router already nested under
// /api/v1/operators/{operatorID} by app.go -- an operator sees deployments
// running on its own clusters, read-only.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorPermission("operator.deployments.view")).Get("/deployments", h.ListOperatorDeployments)
	r.With(authz.RequireOperatorPermission("operator.deployments.view")).Get("/deployments/{deploymentID}/events", h.ListOperatorDeploymentEvents)
}

// MountMachineFacing registers the two routes a cluster agent itself calls
// for deployment execution -- neither carries a user session, mirroring
// Milestone 6's MountMachineFacing for the same reason (an agent is not a
// user). Both are certificate-signature authenticated, verified inside the
// handler/service, not by any session middleware.
func MountMachineFacing(r chi.Router, h *Handlers) {
	r.Get("/api/v1/cluster-agents/{clusterAgentID}/deployments/{deploymentID}/secrets", h.AgentFetchSecrets)
	r.Post("/api/v1/cluster-agents/{clusterAgentID}/control-messages/{messageID}/command-result", h.AgentReportCommandResult)
}
