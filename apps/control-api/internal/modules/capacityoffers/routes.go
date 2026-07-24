package capacityoffers

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountOperatorScoped registers onto a router already nested under
// /api/v1/operators/{operatorID} by app.go. Reads are available to any
// operator member (matching registry's pattern); writes require
// operator.capacity.manage. Viewing reservations held against the
// operator's own capacity requires the separate operator.reservations.view
// permission, since seeing what a tenant has reserved is a distinct
// disclosure from managing the offers themselves. Bilateral agreements and
// capacity offer grants (Milestone 12: Federated Capacity Exchange) are
// gated by operator.agreements.manage -- seeded in Milestone 1
// ("Manage operator-enterprise agreements") and never enforced for real
// until this migration, the richest "roles anticipate milestones" case yet.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorMembership()).Get("/capacity-offers", h.ListOffers)
	r.With(authz.RequireOperatorMembership()).Get("/capacity-offers/{offerID}", h.GetOffer)
	r.With(authz.RequireOperatorPermission("operator.capacity.manage")).Post("/capacity-offers", h.CreateOffer)
	r.With(authz.RequireOperatorPermission("operator.capacity.manage")).Patch("/capacity-offers/{offerID}", h.UpdateOffer)

	r.With(authz.RequireOperatorPermission("operator.reservations.view")).Get("/capacity-reservations", h.ListReservations)

	r.With(authz.RequireOperatorPermission("operator.agreements.manage")).Post("/bilateral-agreements", h.CreateAgreement)
	r.With(authz.RequireOperatorMembership()).Get("/bilateral-agreements", h.ListAgreements)
	r.With(authz.RequireOperatorPermission("operator.agreements.manage")).Post("/bilateral-agreements/{agreementID}/terminate", h.TerminateAgreement)

	r.With(authz.RequireOperatorPermission("operator.agreements.manage")).Post("/capacity-offers/{offerID}/grants", h.CreateGrant)
	r.With(authz.RequireOperatorMembership()).Get("/capacity-offers/{offerID}/grants", h.ListGrantsForOffer)
	r.With(authz.RequireOperatorPermission("operator.agreements.manage")).Post("/capacity-offer-grants/{grantID}/revoke", h.RevokeGrant)
}
