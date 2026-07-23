package models

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-providers", h.ListProviders)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-licences", h.ListLicences)

	r.With(authz.RequireEnterprisePermission("models.view")).Get("/models", h.ListModels)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/models/{modelID}", h.GetModel)
	r.With(authz.RequireEnterprisePermission("models.register")).Post("/models", h.CreateModel)

	r.With(authz.RequireEnterprisePermission("models.view")).Get("/models/{modelID}/versions", h.ListVersions)
	r.With(authz.RequireEnterprisePermission("models.register")).Post("/models/{modelID}/versions", h.CreateDraftVersion)

	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-versions/{versionID}", h.GetVersion)
	r.With(authz.RequireEnterprisePermission("models.edit")).Patch("/model-versions/{versionID}", h.EditDraftVersion)
	r.With(authz.RequireEnterprisePermission("models.register")).Post("/model-versions/{versionID}/request-approval", h.RequestApproval)
	r.With(authz.RequireEnterprisePermission("models.approve")).Post("/model-versions/{versionID}/approve", h.ApproveVersion)
	r.With(authz.RequireEnterprisePermission("models.approve")).Post("/model-versions/{versionID}/reject", h.RejectVersion)
	r.With(authz.RequireEnterprisePermission("models.retire")).Post("/model-versions/{versionID}/retire", h.RetireVersion)
	r.With(authz.RequireEnterprisePermission("models.retire")).Post("/model-versions/{versionID}/revoke", h.RevokeVersion)

	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-versions/{versionID}/capabilities", h.ListCapabilities)
	r.With(authz.RequireEnterprisePermission("models.edit")).Post("/model-versions/{versionID}/capabilities", h.AddCapability)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-versions/{versionID}/benchmarks", h.ListBenchmarks)
	r.With(authz.RequireEnterprisePermission("models.edit")).Post("/model-versions/{versionID}/benchmarks", h.AddBenchmark)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-versions/{versionID}/safety-evaluations", h.ListSafetyEvaluations)
	r.With(authz.RequireEnterprisePermission("models.edit")).Post("/model-versions/{versionID}/safety-evaluations", h.AddSafetyEvaluation)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-versions/{versionID}/deployment-profiles", h.ListDeploymentProfiles)
	r.With(authz.RequireEnterprisePermission("models.edit")).Post("/model-versions/{versionID}/deployment-profiles", h.AddDeploymentProfile)

	r.With(authz.RequireEnterprisePermission("artefacts.view")).Get("/model-versions/{versionID}/artefacts", h.ListArtefactLinks)
	r.With(authz.RequireEnterprisePermission("models.edit")).Post("/model-versions/{versionID}/artefacts", h.LinkArtefact)
}
