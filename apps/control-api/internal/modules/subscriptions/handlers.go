package subscriptions

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/apierror"
)

type Handlers struct {
	svc    *Service
	logger *slog.Logger
}

func NewHandlers(svc *Service, logger *slog.Logger) *Handlers {
	return &Handlers{svc: svc, logger: logger}
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func (h *Handlers) GetEnterpriseEntitlements(w http.ResponseWriter, r *http.Request) {
	ent, err := h.svc.GetEnterpriseEntitlements(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to load entitlements", err))
		return
	}
	if scopedTx, ok := rbac.TxFromContext(r.Context()); ok {
		_ = scopedTx.Commit(r.Context())
	}
	writeJSON(w, http.StatusOK, ent)
}

func (h *Handlers) GetOperatorEntitlements(w http.ResponseWriter, r *http.Request) {
	ent, err := h.svc.GetOperatorEntitlements(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to load entitlements", err))
		return
	}
	if scopedTx, ok := rbac.TxFromContext(r.Context()); ok {
		_ = scopedTx.Commit(r.Context())
	}
	writeJSON(w, http.StatusOK, ent)
}

// MountEnterpriseScoped registers the "my entitlements" view onto a router
// already nested under /api/v1/enterprises/{tenantID} by main.go, alongside
// the tenancy module's own tenant-scoped routes. main.go applies
// httpserver.RequireAuth() once for the whole nested group -- it must not
// be repeated here (chi panics if Use() is called after routes already
// exist on the router).
func MountEnterpriseScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterpriseMembership()).Get("/subscription", h.GetEnterpriseEntitlements)
}

// MountOperatorScoped is the operator-scope equivalent of MountEnterpriseScoped.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorMembership()).Get("/subscription", h.GetOperatorEntitlements)
}
