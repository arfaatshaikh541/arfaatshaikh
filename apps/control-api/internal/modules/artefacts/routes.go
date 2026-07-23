package artefacts

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("artefacts.view")).Get("/artefacts", h.ListArtefacts)
	r.With(authz.RequireEnterprisePermission("artefacts.view")).Get("/artefacts/{artefactID}", h.GetArtefact)
	r.With(authz.RequireEnterprisePermission("artefacts.upload")).Post("/artefacts", h.AuthoriseUpload)
	r.With(authz.RequireEnterprisePermission("artefacts.upload")).Post("/artefacts/{artefactID}/complete", h.CompleteUpload)
	r.With(authz.RequireEnterprisePermission("artefacts.download")).Post("/artefacts/{artefactID}/download", h.RequestDownload)
	r.With(authz.RequireEnterprisePermission("artefacts.delete")).Delete("/artefacts/{artefactID}", h.DeleteArtefact)
	r.With(authz.RequireEnterprisePermission("artefacts.delete")).Post("/artefacts/{artefactID}/malware-scan-result", h.MarkMalwareScanResult)
}
