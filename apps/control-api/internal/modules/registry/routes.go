package registry

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/httpserver"
)

// MountTopLevel registers the global jurisdiction/region taxonomy routes.
// Reads require only an authenticated session -- this is non-sensitive
// reference data every enterprise and operator user needs (an enterprise
// selecting a placement region, an operator registering a data centre);
// writes require platform.regions.manage, since the taxonomy is
// platform-curated, not operator- or tenant-owned.
func MountTopLevel(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.Route("/api/v1/jurisdictions", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		r.Get("/", h.ListJurisdictions)
		r.With(authz.RequirePlatformPermission("platform.regions.manage")).Post("/", h.CreateJurisdiction)
	})
	r.Route("/api/v1/regions", func(r chi.Router) {
		r.Use(httpserver.RequireAuth())
		r.Get("/", h.ListRegions)
		r.With(authz.RequirePlatformPermission("platform.regions.manage")).Post("/", h.CreateRegion)
	})
}

// MountOperatorScoped registers onto a router already nested under
// /api/v1/operators/{operatorID} by app.go, alongside other modules'
// operator-scoped routes. Reads are available to any operator member
// (matching the Milestone 1 GetTenant/ListMembers pattern); writes require
// the specific operator.* permission that already exists for that resource
// family in the seeded permission matrix.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorMembership()).Get("/contracts", h.ListOperatorContracts)
	r.With(authz.RequireOperatorPermission("operator.profile.manage")).Post("/contracts", h.CreateOperatorContract)

	r.With(authz.RequireOperatorMembership()).Get("/data-centres", h.ListDataCentres)
	r.With(authz.RequireOperatorPermission("operator.locations.manage")).Post("/data-centres", h.CreateDataCentre)

	r.With(authz.RequireOperatorMembership()).Get("/edge-sites", h.ListEdgeSites)
	r.With(authz.RequireOperatorPermission("operator.locations.manage")).Post("/edge-sites", h.CreateEdgeSite)

	r.With(authz.RequireOperatorMembership()).Get("/clusters", h.ListClusters)
	r.With(authz.RequireOperatorPermission("operator.clusters.manage")).Post("/clusters", h.CreateCluster)

	r.With(authz.RequireOperatorMembership()).Get("/node-pools", h.ListNodePools)
	r.With(authz.RequireOperatorPermission("operator.clusters.manage")).Post("/node-pools", h.CreateNodePool)

	r.With(authz.RequireOperatorMembership()).Get("/accelerators", h.ListAccelerators)
	r.With(authz.RequireOperatorPermission("operator.clusters.manage")).Post("/accelerators", h.CreateAccelerator)

	r.With(authz.RequireOperatorMembership()).Get("/storage-pools", h.ListStoragePools)
	r.With(authz.RequireOperatorPermission("operator.locations.manage")).Post("/storage-pools", h.CreateStoragePool)

	r.With(authz.RequireOperatorMembership()).Get("/network-capabilities", h.ListNetworkCapabilities)
	r.With(authz.RequireOperatorPermission("operator.locations.manage")).Post("/network-capabilities", h.CreateNetworkCapability)
}
