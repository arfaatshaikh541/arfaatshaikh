package tenancy

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/apierror"
	"gridkeep/control-api/internal/platform/httpserver"
)

type Handlers struct {
	svc    *Service
	logger *slog.Logger
}

func NewHandlers(svc *Service, logger *slog.Logger) *Handlers {
	return &Handlers{svc: svc, logger: logger}
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

type createTenantRequest struct {
	LegalName   string `json:"legal_name"`
	DisplayName string `json:"display_name"`
	Country     string `json:"country"`
}

func (h *Handlers) CreateTenant(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	var req createTenantRequest
	if err := decodeJSON(r, &req); err != nil || req.LegalName == "" || req.Country == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	displayName := req.DisplayName
	if displayName == "" {
		displayName = req.LegalName
	}
	tenant, err := h.svc.CreateTenant(r.Context(), authUser.UserID, req.LegalName, displayName, req.Country)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to create tenant", err))
		return
	}
	writeJSON(w, http.StatusCreated, tenant)
}

func (h *Handlers) GetTenant(w http.ResponseWriter, r *http.Request) {
	tenant, err := h.svc.GetTenant(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to load tenant", err))
		return
	}
	if scopedTx, ok := rbac.TxFromContext(r.Context()); ok {
		_ = scopedTx.Commit(r.Context())
	}
	writeJSON(w, http.StatusOK, tenant)
}

type updateTenantRequest struct {
	DisplayName string `json:"display_name"`
}

func (h *Handlers) UpdateTenant(w http.ResponseWriter, r *http.Request) {
	var req updateTenantRequest
	if err := decodeJSON(r, &req); err != nil || req.DisplayName == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.UpdateTenantSettings(r.Context(), req.DisplayName); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to update tenant", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "updated"})
}

func (h *Handlers) ListMembers(w http.ResponseWriter, r *http.Request) {
	members, err := h.svc.ListMembers(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list members", err))
		return
	}
	if scopedTx, ok := rbac.TxFromContext(r.Context()); ok {
		_ = scopedTx.Commit(r.Context())
	}
	writeJSON(w, http.StatusOK, members)
}

func (h *Handlers) ListMyMemberships(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	memberships, err := h.svc.ListMyMemberships(r.Context(), authUser.UserID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list memberships", err))
		return
	}
	writeJSON(w, http.StatusOK, memberships)
}

type createInvitationRequest struct {
	Email   string `json:"email"`
	RoleKey string `json:"role_key"`
}

func (h *Handlers) CreateInvitation(w http.ResponseWriter, r *http.Request) {
	var req createInvitationRequest
	if err := decodeJSON(r, &req); err != nil || req.Email == "" || req.RoleKey == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.CreateInvitation(r.Context(), req.Email, req.RoleKey); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to create invitation", err))
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{"status": "invitation_sent"})
}

type acceptInvitationRequest struct {
	Token string `json:"token"`
}

func (h *Handlers) AcceptInvitation(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	var req acceptInvitationRequest
	if err := decodeJSON(r, &req); err != nil || req.Token == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	tenantID, err := h.svc.AcceptInvitation(r.Context(), authUser.UserID, req.Token)
	if err != nil {
		if errors.Is(err, ErrInvalidInvitation) {
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, "This invitation is invalid or has expired."))
			return
		}
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to accept invitation", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"enterprise_tenant_id": tenantID})
}
