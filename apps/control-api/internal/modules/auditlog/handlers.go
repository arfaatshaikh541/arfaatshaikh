package auditlog

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

func (h *Handlers) ListEnterpriseEvents(w http.ResponseWriter, r *http.Request) {
	events, err := h.svc.ListEnterpriseEvents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list audit events", err))
		return
	}
	if scopedTx, ok := rbac.TxFromContext(r.Context()); ok {
		_ = scopedTx.Commit(r.Context())
	}
	writeJSON(w, http.StatusOK, events)
}

func (h *Handlers) ListOperatorEvents(w http.ResponseWriter, r *http.Request) {
	events, err := h.svc.ListOperatorEvents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list audit events", err))
		return
	}
	if scopedTx, ok := rbac.TxFromContext(r.Context()); ok {
		_ = scopedTx.Commit(r.Context())
	}
	writeJSON(w, http.StatusOK, events)
}

func (h *Handlers) ListPlatformEvents(w http.ResponseWriter, r *http.Request) {
	events, err := h.svc.ListPlatformEvents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list audit events", err))
		return
	}
	if scopedTx, ok := rbac.TxFromContext(r.Context()); ok {
		_ = scopedTx.Commit(r.Context())
	}
	writeJSON(w, http.StatusOK, events)
}

// MountEnterpriseScoped registers onto a router nested under
// /api/v1/enterprises/{tenantID}.
func MountEnterpriseScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("audit.view")).Get("/audit", h.ListEnterpriseEvents)
}

// MountOperatorScoped registers onto a router nested under
// /api/v1/operators/{operatorID}.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorPermission("operator.audit.view")).Get("/audit", h.ListOperatorEvents)
}

// MountPlatformScoped registers onto a router nested under /api/v1/platform.
func MountPlatformScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequirePlatformPermission("platform.audit.view")).Get("/audit", h.ListPlatformEvents)
}
