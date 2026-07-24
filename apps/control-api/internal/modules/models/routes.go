package models

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/httpserver"
)

// MountTopLevel registers the global model provider catalogue's onboarding
// routes -- provider records are platform-curated reference data, not
// tenant- or operator-owned, the same shape registry.MountTopLevel already
// established for jurisdictions/regions.
func MountTopLevel(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.Route("/api/v1/model-providers", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		// A top-level read alongside the tenant-scoped one in
		// MountTenantScoped below -- Milestone 15's platform portal needs to
		// browse existing providers (to suspend/reactivate them) without
		// being nested under any one tenant, the same "reads require only an
		// authenticated session" reasoning registry.MountTopLevel already
		// applies to jurisdictions/regions.
		r.Get("/", h.ListProviders)
		r.With(authz.RequirePlatformPermission("platform.model_catalogue.manage")).Post("/", h.CreateProvider)
		r.With(authz.RequirePlatformPermission("platform.model_catalogue.manage")).Post("/{providerID}/suspend", h.SuspendProvider)
		r.With(authz.RequirePlatformPermission("platform.model_catalogue.manage")).Post("/{providerID}/reactivate", h.ReactivateProvider)
	})
}

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

	// Milestone 13: AI Model Exchange. models.publish gates every
	// commercialization action (listing a version, granting/revoking another
	// tenant's access) -- a permission seeded in Milestone 1 and never
	// enforced until now, the same "dormant since migration 0002" pattern
	// operator.agreements.manage was for Milestone 12.
	r.With(authz.RequireEnterprisePermission("models.publish")).Post("/model-versions/{versionID}/publish", h.PublishVersion)
	r.With(authz.RequireEnterprisePermission("models.publish")).Post("/model-versions/{versionID}/unpublish", h.UnpublishVersion)
	r.With(authz.RequireEnterprisePermission("models.publish")).Post("/model-versions/{versionID}/access-grants", h.CreateAccessGrant)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-versions/{versionID}/access-grants", h.ListAccessGrantsForVersion)
	r.With(authz.RequireEnterprisePermission("models.publish")).Post("/model-access-grants/{grantID}/revoke", h.RevokeAccessGrant)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-access-grants/received", h.ListMyModelAccessGrants)

	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-marketplace/versions", h.ListMarketplaceModelVersions)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-marketplace/versions/{versionID}", h.GetMarketplaceModelVersion)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-marketplace/versions/{versionID}/capabilities", h.ListMarketplaceCapabilities)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-marketplace/versions/{versionID}/benchmarks", h.ListMarketplaceBenchmarks)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-marketplace/versions/{versionID}/safety-evaluations", h.ListMarketplaceSafetyEvaluations)
	r.With(authz.RequireEnterprisePermission("models.view")).Get("/model-marketplace/versions/{versionID}/deployment-profiles", h.ListMarketplaceDeploymentProfiles)
}
