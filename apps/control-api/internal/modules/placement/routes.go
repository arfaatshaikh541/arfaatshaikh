package placement

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("capacity.view")).Get("/capacity-offers", h.ListActiveOffers)
	r.With(authz.RequireEnterprisePermission("capacity.view")).Get("/bilateral-agreements", h.ListMyAgreements)

	r.With(authz.RequireEnterprisePermission("reservations.create")).Post("/placement-requests", h.EvaluatePlacement)
	r.With(authz.RequireEnterprisePermission("capacity.view")).Get("/placement-requests", h.ListPlacementRequests)
	r.With(authz.RequireEnterprisePermission("capacity.view")).Get("/placement-requests/{requestID}/evaluations", h.ListEvaluations)

	r.With(authz.RequireEnterprisePermission("capacity.view")).Get("/capacity-reservations", h.ListReservations)
	r.With(authz.RequireEnterprisePermission("reservations.approve")).Post("/capacity-reservations/{reservationID}/approve-commit", h.ApproveCommitReservation)
	r.With(authz.RequireEnterprisePermission("reservations.cancel")).Post("/capacity-reservations/{reservationID}/cancel", h.CancelReservation)
}
