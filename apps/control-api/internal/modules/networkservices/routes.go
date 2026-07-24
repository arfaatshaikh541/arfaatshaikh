package networkservices

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go. Reservation lifecycle actions
// deliberately reuse the already-generically-named reservations.create/
// reservations.cancel permissions rather than minting network-specific
// equivalents -- see migration 0031's header comment.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("network.view")).Get("/network-service-offers", h.ListActiveOffers)

	r.With(authz.RequireEnterprisePermission("reservations.create")).Post("/network-service-requests", h.EvaluateAndReserve)
	r.With(authz.RequireEnterprisePermission("network.view")).Get("/network-service-requests", h.ListRequests)
	r.With(authz.RequireEnterprisePermission("network.view")).Get("/network-service-requests/{requestID}/evaluations", h.ListEvaluations)

	r.With(authz.RequireEnterprisePermission("network.view")).Get("/network-reservations", h.ListTenantReservations)
	r.With(authz.RequireEnterprisePermission("reservations.cancel")).Post("/network-reservations/{reservationID}/cancel", h.CancelReservation)

	r.With(authz.RequireEnterprisePermission("network.view")).Get("/network-health-events", h.ListTenantHealthEvents)
}

// MountOperatorScoped registers onto a router already nested under
// /api/v1/operators/{operatorID} by app.go. Reads are available to any
// operator member (matching internal/modules/capacityoffers' pattern);
// writes require operator.network.manage. Viewing reservations held
// against the operator's own offers reuses operator.reservations.view --
// the same permission internal/modules/capacityoffers already gates its
// own reservation visibility with, for the identical reason.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorMembership()).Get("/network-service-offers", h.ListOffers)
	r.With(authz.RequireOperatorMembership()).Get("/network-service-offers/{offerID}", h.GetOffer)
	r.With(authz.RequireOperatorPermission("operator.network.manage")).Post("/network-service-offers", h.CreateOffer)
	r.With(authz.RequireOperatorPermission("operator.network.manage")).Patch("/network-service-offers/{offerID}", h.UpdateOffer)

	r.With(authz.RequireOperatorPermission("operator.reservations.view")).Get("/network-reservations", h.ListOperatorReservations)
	r.With(authz.RequireOperatorPermission("operator.reservations.view")).Get("/network-health-events", h.ListOperatorHealthEvents)
}

// MountMachineFacing registers the one route a cluster agent itself calls
// to report a network_service_provision command's outcome -- no user
// session, certificate-signature authenticated, mirroring
// internal/modules/deployments' MountMachineFacing for the same reason.
func MountMachineFacing(r chi.Router, h *Handlers) {
	r.Post("/api/v1/cluster-agents/{clusterAgentID}/control-messages/{messageID}/network-provision-result", h.AgentReportProvisionResult)
}
