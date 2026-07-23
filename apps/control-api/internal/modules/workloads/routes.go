package workloads

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("workloads.view")).Get("/workloads", h.ListWorkloads)
	r.With(authz.RequireEnterprisePermission("workloads.view")).Get("/workloads/{workloadID}", h.GetWorkload)
	r.With(authz.RequireEnterprisePermission("workloads.create")).Post("/workloads", h.CreateWorkload)
	r.With(authz.RequireEnterprisePermission("workloads.retire")).Post("/workloads/{workloadID}/retire", h.RetireWorkload)

	r.With(authz.RequireEnterprisePermission("workloads.view")).Get("/workloads/{workloadID}/versions", h.ListVersions)
	r.With(authz.RequireEnterprisePermission("workloads.create")).Post("/workloads/{workloadID}/versions", h.CreateDraftVersion)

	r.With(authz.RequireEnterprisePermission("workloads.view")).Get("/workload-versions/{versionID}", h.GetVersion)
	r.With(authz.RequireEnterprisePermission("workloads.edit")).Patch("/workload-versions/{versionID}", h.EditDraftVersion)
	r.With(authz.RequireEnterprisePermission("workloads.publish")).Post("/workload-versions/{versionID}/request-publish", h.RequestPublish)
	r.With(authz.RequireEnterprisePermission("workloads.publish")).Post("/workload-versions/{versionID}/approve-publish", h.ApprovePublish)
	r.With(authz.RequireEnterprisePermission("workloads.publish")).Post("/workload-versions/{versionID}/deprecate", h.DeprecateVersion)
	r.With(authz.RequireEnterprisePermission("workloads.retire")).Post("/workload-versions/{versionID}/retire", h.RetireVersion)

	r.With(authz.RequireEnterprisePermission("workloads.view")).Get("/workload-versions/{versionID}/components", h.ListComponents)
	r.With(authz.RequireEnterprisePermission("workloads.edit")).Post("/workload-versions/{versionID}/components", h.AddComponent)
	r.With(authz.RequireEnterprisePermission("workloads.view")).Get("/workload-components/{componentID}/health-checks", h.ListHealthChecks)
	r.With(authz.RequireEnterprisePermission("workloads.edit")).Post("/workload-components/{componentID}/health-checks", h.AddHealthCheck)

	r.With(authz.RequireEnterprisePermission("workloads.view")).Get("/workload-versions/{versionID}/artefacts", h.ListArtefactLinks)
	r.With(authz.RequireEnterprisePermission("workloads.edit")).Post("/workload-versions/{versionID}/artefacts", h.LinkArtefact)
	r.With(authz.RequireEnterprisePermission("sbom.view")).Get("/workload-versions/{versionID}/sboms", h.ListSBOMLinks)
	r.With(authz.RequireEnterprisePermission("workloads.edit")).Post("/workload-versions/{versionID}/sboms", h.LinkSBOM)
}
