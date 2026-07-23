package policies

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go, using the policies.* enterprise
// permissions seeded in Milestone 1 (docs/security/permission-matrix.md)
// and enforced for real here for the first time.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("policies.view")).Get("/policies", h.ListPolicies)
	r.With(authz.RequireEnterprisePermission("policies.view")).Get("/policies/{policyID}", h.GetPolicy)
	r.With(authz.RequireEnterprisePermission("policies.view")).Get("/policies/by-key/{policyKey}/versions", h.ListVersions)
	r.With(authz.RequireEnterprisePermission("policies.create")).Post("/policies", h.CreateDraft)
	r.With(authz.RequireEnterprisePermission("policies.edit")).Patch("/policies/{policyID}", h.EditDraft)
	r.With(authz.RequireEnterprisePermission("policies.publish")).Post("/policies/{policyID}/request-publish", h.RequestPublish)
	r.With(authz.RequireEnterprisePermission("policies.approve")).Post("/policies/{policyID}/approve-publish", h.ApprovePublish)
	r.With(authz.RequireEnterprisePermission("policies.rollback")).Post("/policies/by-key/{policyKey}/rollback", h.Rollback)
	r.With(authz.RequireEnterprisePermission("policies.simulate")).Post("/policies/{policyID}/simulate", h.Simulate)
	r.With(authz.RequireEnterprisePermission("policies.view")).Post("/policies/{policyID}/evaluate", h.Evaluate)
	r.With(authz.RequireEnterprisePermission("policies.view")).Get("/policy-evaluations", h.ListEvaluationRecords)
}
