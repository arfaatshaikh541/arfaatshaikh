package platformadmin

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/modules/subscriptions"
	"gridkeep/control-api/internal/platform/apierror"
	"gridkeep/control-api/internal/platform/httpserver"
)

type Handlers struct {
	svc     *Service
	subsSvc *subscriptions.Service
	logger  *slog.Logger
}

func NewHandlers(svc *Service, subsSvc *subscriptions.Service, logger *slog.Logger) *Handlers {
	return &Handlers{svc: svc, subsSvc: subsSvc, logger: logger}
}

func decodeJSON(r *http.Request, dst any) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	return dec.Decode(dst)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func commitScope(r *http.Request) {
	if scopedTx, ok := rbac.TxFromContext(r.Context()); ok {
		_ = scopedTx.Commit(r.Context())
	}
}

func actorUserID(r *http.Request) (uuid.UUID, bool) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		return uuid.Nil, false
	}
	return authUser.UserID, true
}

func (h *Handlers) ListTenants(w http.ResponseWriter, r *http.Request) {
	tenants, err := h.svc.ListTenants(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list tenants", err))
		return
	}
	commitScope(r)
	writeJSON(w, http.StatusOK, tenants)
}

type setStatusRequest struct {
	Status string `json:"status"`
}

func (h *Handlers) SetTenantStatus(w http.ResponseWriter, r *http.Request) {
	actor, ok := actorUserID(r)
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	tenantID, err := uuid.Parse(chi.URLParam(r, "tenantID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req setStatusRequest
	if err := decodeJSON(r, &req); err != nil || req.Status == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.SetTenantStatus(r.Context(), actor, tenantID, req.Status); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to update tenant status", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "updated"})
}

type assignPlanRequest struct {
	PlanKey string `json:"plan_key"`
}

func (h *Handlers) AssignEnterprisePlan(w http.ResponseWriter, r *http.Request) {
	actor, ok := actorUserID(r)
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	tenantID, err := uuid.Parse(chi.URLParam(r, "tenantID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req assignPlanRequest
	if err := decodeJSON(r, &req); err != nil || req.PlanKey == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.subsSvc.AssignEnterprisePlan(r.Context(), actor, tenantID, req.PlanKey); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to assign plan", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "plan_assigned"})
}

func (h *Handlers) ListOperators(w http.ResponseWriter, r *http.Request) {
	ops, err := h.svc.ListOperators(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list operators", err))
		return
	}
	commitScope(r)
	writeJSON(w, http.StatusOK, ops)
}

func (h *Handlers) SetOperatorStatus(w http.ResponseWriter, r *http.Request) {
	actor, ok := actorUserID(r)
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	operatorID, err := uuid.Parse(chi.URLParam(r, "operatorID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req setStatusRequest
	if err := decodeJSON(r, &req); err != nil || req.Status == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.SetOperatorStatus(r.Context(), actor, operatorID, req.Status); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to update operator status", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "updated"})
}

type setTrustLevelRequest struct {
	TrustLevel string `json:"trust_level"`
}

func (h *Handlers) SetOperatorTrustLevel(w http.ResponseWriter, r *http.Request) {
	actor, ok := actorUserID(r)
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	operatorID, err := uuid.Parse(chi.URLParam(r, "operatorID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req setTrustLevelRequest
	if err := decodeJSON(r, &req); err != nil || req.TrustLevel == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.SetOperatorTrustLevel(r.Context(), actor, operatorID, req.TrustLevel); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to update operator trust level", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "updated"})
}

func (h *Handlers) AssignOperatorPlan(w http.ResponseWriter, r *http.Request) {
	actor, ok := actorUserID(r)
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	operatorID, err := uuid.Parse(chi.URLParam(r, "operatorID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req assignPlanRequest
	if err := decodeJSON(r, &req); err != nil || req.PlanKey == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.subsSvc.AssignOperatorPlan(r.Context(), actor, operatorID, req.PlanKey); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to assign plan", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "plan_assigned"})
}

type requestSupportAccessRequest struct {
	ScopeType string    `json:"scope_type"`
	ScopeID   uuid.UUID `json:"scope_id"`
	Reason    string    `json:"reason"`
}

func (h *Handlers) RequestSupportAccessGrant(w http.ResponseWriter, r *http.Request) {
	actor, ok := actorUserID(r)
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	var req requestSupportAccessRequest
	if err := decodeJSON(r, &req); err != nil || req.Reason == "" || (req.ScopeType != "enterprise" && req.ScopeType != "operator") {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	id, err := h.svc.RequestSupportAccessGrant(r.Context(), actor, req.ScopeType, req.ScopeID, req.Reason)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to request support access", err))
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{"id": id})
}

func (h *Handlers) ApproveSupportAccessGrant(w http.ResponseWriter, r *http.Request) {
	actor, ok := actorUserID(r)
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	grantID, err := uuid.Parse(chi.URLParam(r, "grantID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.ApproveSupportAccessGrant(r.Context(), actor, grantID); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusConflict, apierror.CodeConflict, "Unable to approve: grant not found, already decided, or you are the requester (dual control required)."))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "approved"})
}

func (h *Handlers) RevokeSupportAccessGrant(w http.ResponseWriter, r *http.Request) {
	actor, ok := actorUserID(r)
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	grantID, err := uuid.Parse(chi.URLParam(r, "grantID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.RevokeSupportAccessGrant(r.Context(), actor, grantID); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to revoke support access", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "revoked"})
}

func (h *Handlers) ListSupportAccessGrants(w http.ResponseWriter, r *http.Request) {
	grants, err := h.svc.ListSupportAccessGrants(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list support access grants", err))
		return
	}
	commitScope(r)
	writeJSON(w, http.StatusOK, grants)
}
