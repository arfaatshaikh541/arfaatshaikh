package images

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountPlatformScoped registers onto a router already nested under
// /api/v1/platform by app.go -- the platform-curated approved-registry
// allowlist, the same kind of global reference data as
// platform.regions.manage in Milestone 2.
func MountPlatformScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequirePlatformPermission("platform.container_registries.manage")).Get("/container-registries", h.ListApprovedRegistries)
	r.With(authz.RequirePlatformPermission("platform.container_registries.manage")).Post("/container-registries", h.AddApprovedRegistry)
	r.With(authz.RequirePlatformPermission("platform.container_registries.manage")).Patch("/container-registries/{registryID}", h.SetApprovedRegistryActive)
}

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("images.view")).Get("/images", h.ListImages)
	r.With(authz.RequireEnterprisePermission("images.view")).Get("/images/{imageID}", h.GetImage)
	r.With(authz.RequireEnterprisePermission("images.register")).Post("/images", h.RegisterImage)
	r.With(authz.RequireEnterprisePermission("images.approve")).Post("/images/{imageID}/approve", h.ApproveImage)
	r.With(authz.RequireEnterprisePermission("images.revoke")).Post("/images/{imageID}/revoke", h.RevokeImage)

	r.With(authz.RequireEnterprisePermission("images.view")).Get("/images/{imageID}/signatures", h.ListSignatures)
	r.With(authz.RequireEnterprisePermission("images.register")).Post("/images/{imageID}/signatures", h.RecordSignature)

	r.With(authz.RequireEnterprisePermission("images.view")).Get("/images/{imageID}/provenance", h.GetProvenance)
	r.With(authz.RequireEnterprisePermission("images.register")).Put("/images/{imageID}/provenance", h.RecordProvenance)

	r.With(authz.RequireEnterprisePermission("sbom.view")).Get("/images/{imageID}/sboms", h.ListSBOMs)
	r.With(authz.RequireEnterprisePermission("images.register")).Post("/images/{imageID}/sboms", h.IngestSBOM)

	r.With(authz.RequireEnterprisePermission("vulnerabilities.view")).Get("/images/{imageID}/vulnerability-scans", h.ListVulnerabilityScans)
	r.With(authz.RequireEnterprisePermission("images.register")).Post("/images/{imageID}/vulnerability-scans", h.IngestVulnerabilityScan)
	r.With(authz.RequireEnterprisePermission("vulnerabilities.view")).Get("/vulnerability-scans/{scanID}/findings", h.ListFindings)

	r.With(authz.RequireEnterprisePermission("vulnerabilities.view")).Get("/vulnerability-policy", h.GetVulnerabilityPolicy)
	r.With(authz.RequireEnterprisePermission("images.approve")).Put("/vulnerability-policy", h.UpdateVulnerabilityPolicy)

	r.With(authz.RequireEnterprisePermission("vulnerabilities.view")).Get("/images/{imageID}/vulnerability-exceptions", h.ListExceptions)
	r.With(authz.RequireEnterprisePermission("vulnerability_exceptions.request")).Post("/images/{imageID}/vulnerability-exceptions", h.RequestException)
	r.With(authz.RequireEnterprisePermission("vulnerability_exceptions.approve")).Post("/vulnerability-exceptions/{exceptionID}/approve", h.ApproveException)
	r.With(authz.RequireEnterprisePermission("vulnerability_exceptions.approve")).Post("/vulnerability-exceptions/{exceptionID}/reject", h.RejectException)
}
