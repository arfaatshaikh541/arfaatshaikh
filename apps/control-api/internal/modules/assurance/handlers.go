package assurance

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gridkeep/control-api/internal/platform/apierror"
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

func writeServiceError(w http.ResponseWriter, r *http.Request, logger *slog.Logger, err error) {
	switch {
	case errors.Is(err, ErrSLONotActive), errors.Is(err, ErrIncidentNotOpen), errors.Is(err, ErrIncidentNotOpenOrAcknowledged):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrSLONotFound), errors.Is(err, ErrIncidentNotFound), errors.Is(err, ErrAlertRuleNotFound):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusNotFound, apierror.CodeNotFound, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "assurance operation failed", err))
	}
}

func parseOptionalResourceID(s string) (*uuid.UUID, error) {
	if s == "" {
		return nil, nil
	}
	id, err := uuid.Parse(s)
	if err != nil {
		return nil, err
	}
	return &id, nil
}

func parseOptionalString(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// ---------------------------------------------------------------------
// SLOs
// ---------------------------------------------------------------------

type createSLORequest struct {
	Name             string  `json:"name"`
	MetricSource     string  `json:"metric_source"`
	ResourceType     string  `json:"resource_type,omitempty"`
	ResourceID       string  `json:"resource_id,omitempty"`
	TargetPercentage float64 `json:"target_percentage"`
	WindowDays       int     `json:"window_days"`
}

func decodeSLORequest(r *http.Request) (CreateSLOInput, error) {
	var req createSLORequest
	if err := decodeJSON(r, &req); err != nil || req.Name == "" || req.MetricSource == "" ||
		req.TargetPercentage <= 0 || req.TargetPercentage > 100 || req.WindowDays <= 0 {
		return CreateSLOInput{}, apierror.ErrValidation
	}
	resourceID, err := parseOptionalResourceID(req.ResourceID)
	if err != nil {
		return CreateSLOInput{}, apierror.ErrValidation
	}
	return CreateSLOInput{
		Name: req.Name, MetricSource: req.MetricSource, ResourceType: parseOptionalString(req.ResourceType),
		ResourceID: resourceID, TargetPercentage: req.TargetPercentage, WindowDays: req.WindowDays,
	}, nil
}

func (h *Handlers) CreateSLO(w http.ResponseWriter, r *http.Request) {
	in, err := decodeSLORequest(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	slo, err := h.svc.CreateSLO(r.Context(), in)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, slo)
}

func (h *Handlers) ListSLOs(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListSLOs(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list SLOs", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func sloIDParam(r *http.Request) (uuid.UUID, error) {
	return uuid.Parse(chi.URLParam(r, "sloID"))
}

func (h *Handlers) ArchiveSLO(w http.ResponseWriter, r *http.Request) {
	id, err := sloIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.ArchiveSLO(r.Context(), id); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "archived"})
}

func (h *Handlers) EvaluateSLO(w http.ResponseWriter, r *http.Request) {
	id, err := sloIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	eval, err := h.svc.EvaluateSLO(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, eval)
}

func (h *Handlers) ListSLOEvaluations(w http.ResponseWriter, r *http.Request) {
	id, err := sloIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListSLOEvaluations(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) CreateOperatorSLO(w http.ResponseWriter, r *http.Request) {
	in, err := decodeSLORequest(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	slo, err := h.svc.CreateOperatorSLO(r.Context(), in)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, slo)
}

func (h *Handlers) ListOperatorSLOs(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorSLOs(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list SLOs", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) ArchiveOperatorSLO(w http.ResponseWriter, r *http.Request) {
	id, err := sloIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.ArchiveOperatorSLO(r.Context(), id); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "archived"})
}

func (h *Handlers) EvaluateOperatorSLO(w http.ResponseWriter, r *http.Request) {
	id, err := sloIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	eval, err := h.svc.EvaluateOperatorSLO(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, eval)
}

func (h *Handlers) ListOperatorSLOEvaluations(w http.ResponseWriter, r *http.Request) {
	id, err := sloIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListOperatorSLOEvaluations(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Incidents
// ---------------------------------------------------------------------

type createIncidentRequest struct {
	Title        string `json:"title"`
	Description  string `json:"description,omitempty"`
	Severity     string `json:"severity"`
	ResourceType string `json:"resource_type,omitempty"`
	ResourceID   string `json:"resource_id,omitempty"`
}

func decodeIncidentRequest(r *http.Request) (CreateIncidentInput, error) {
	var req createIncidentRequest
	if err := decodeJSON(r, &req); err != nil || req.Title == "" || req.Severity == "" {
		return CreateIncidentInput{}, apierror.ErrValidation
	}
	resourceID, err := parseOptionalResourceID(req.ResourceID)
	if err != nil {
		return CreateIncidentInput{}, apierror.ErrValidation
	}
	return CreateIncidentInput{
		Title: req.Title, Description: req.Description, Severity: req.Severity,
		ResourceType: parseOptionalString(req.ResourceType), ResourceID: resourceID,
	}, nil
}

func incidentIDParam(r *http.Request) (uuid.UUID, error) {
	return uuid.Parse(chi.URLParam(r, "incidentID"))
}

func (h *Handlers) CreateIncident(w http.ResponseWriter, r *http.Request) {
	in, err := decodeIncidentRequest(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inc, err := h.svc.CreateIncident(r.Context(), in)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, inc)
}

func (h *Handlers) ListIncidents(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListIncidents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list incidents", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) AcknowledgeIncident(w http.ResponseWriter, r *http.Request) {
	id, err := incidentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inc, err := h.svc.AcknowledgeIncident(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, inc)
}

func (h *Handlers) ResolveIncident(w http.ResponseWriter, r *http.Request) {
	id, err := incidentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inc, err := h.svc.ResolveIncident(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, inc)
}

func (h *Handlers) ListIncidentEvents(w http.ResponseWriter, r *http.Request) {
	id, err := incidentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListIncidentEvents(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) CreateOperatorIncident(w http.ResponseWriter, r *http.Request) {
	in, err := decodeIncidentRequest(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inc, err := h.svc.CreateOperatorIncident(r.Context(), in)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, inc)
}

func (h *Handlers) ListOperatorIncidents(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorIncidents(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list incidents", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) AcknowledgeOperatorIncident(w http.ResponseWriter, r *http.Request) {
	id, err := incidentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inc, err := h.svc.AcknowledgeOperatorIncident(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, inc)
}

func (h *Handlers) ResolveOperatorIncident(w http.ResponseWriter, r *http.Request) {
	id, err := incidentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	inc, err := h.svc.ResolveOperatorIncident(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, inc)
}

func (h *Handlers) ListOperatorIncidentEvents(w http.ResponseWriter, r *http.Request) {
	id, err := incidentIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListOperatorIncidentEvents(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Alert rules and alerts
// ---------------------------------------------------------------------

type createAlertRuleRequest struct {
	Name         string  `json:"name"`
	MetricSource string  `json:"metric_source"`
	ResourceType string  `json:"resource_type,omitempty"`
	ResourceID   string  `json:"resource_id,omitempty"`
	Comparison   string  `json:"comparison"`
	Threshold    float64 `json:"threshold"`
	Severity     string  `json:"severity"`
}

func decodeAlertRuleRequest(r *http.Request) (CreateAlertRuleInput, error) {
	var req createAlertRuleRequest
	if err := decodeJSON(r, &req); err != nil || req.Name == "" || req.MetricSource == "" ||
		(req.Comparison != "lt" && req.Comparison != "gt") || req.Severity == "" {
		return CreateAlertRuleInput{}, apierror.ErrValidation
	}
	resourceID, err := parseOptionalResourceID(req.ResourceID)
	if err != nil {
		return CreateAlertRuleInput{}, apierror.ErrValidation
	}
	return CreateAlertRuleInput{
		Name: req.Name, MetricSource: req.MetricSource, ResourceType: parseOptionalString(req.ResourceType),
		ResourceID: resourceID, Comparison: req.Comparison, Threshold: req.Threshold, Severity: req.Severity,
	}, nil
}

func alertRuleIDParam(r *http.Request) (uuid.UUID, error) {
	return uuid.Parse(chi.URLParam(r, "ruleID"))
}

func (h *Handlers) CreateAlertRule(w http.ResponseWriter, r *http.Request) {
	in, err := decodeAlertRuleRequest(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	rule, err := h.svc.CreateAlertRule(r.Context(), in)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, rule)
}

func (h *Handlers) ListAlertRules(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListAlertRules(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list alert rules", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

type setAlertRuleStatusRequest struct {
	Status string `json:"status"`
}

func (h *Handlers) SetAlertRuleStatus(w http.ResponseWriter, r *http.Request) {
	id, err := alertRuleIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req setAlertRuleStatusRequest
	if err := decodeJSON(r, &req); err != nil || (req.Status != "active" && req.Status != "paused") {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.SetAlertRuleStatus(r.Context(), id, req.Status); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": req.Status})
}

func (h *Handlers) EvaluateAlertRule(w http.ResponseWriter, r *http.Request) {
	id, err := alertRuleIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	alert, err := h.svc.EvaluateAlertRule(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"alert": alert})
}

func (h *Handlers) ListAlerts(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListAlerts(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list alerts", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) CreateOperatorAlertRule(w http.ResponseWriter, r *http.Request) {
	in, err := decodeAlertRuleRequest(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	rule, err := h.svc.CreateOperatorAlertRule(r.Context(), in)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, rule)
}

func (h *Handlers) ListOperatorAlertRules(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorAlertRules(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list alert rules", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) SetOperatorAlertRuleStatus(w http.ResponseWriter, r *http.Request) {
	id, err := alertRuleIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req setAlertRuleStatusRequest
	if err := decodeJSON(r, &req); err != nil || (req.Status != "active" && req.Status != "paused") {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.SetOperatorAlertRuleStatus(r.Context(), id, req.Status); err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": req.Status})
}

func (h *Handlers) EvaluateOperatorAlertRule(w http.ResponseWriter, r *http.Request) {
	id, err := alertRuleIDParam(r)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	alert, err := h.svc.EvaluateOperatorAlertRule(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"alert": alert})
}

func (h *Handlers) ListOperatorAlerts(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListOperatorAlerts(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list alerts", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

// ---------------------------------------------------------------------
// Correlated health and audit correlation
// ---------------------------------------------------------------------

func (h *Handlers) GetCorrelatedHealth(w http.ResponseWriter, r *http.Request) {
	health, err := h.svc.GetCorrelatedHealth(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to compute correlated health", err))
		return
	}
	writeJSON(w, http.StatusOK, health)
}

func (h *Handlers) GetOperatorCorrelatedHealth(w http.ResponseWriter, r *http.Request) {
	health, err := h.svc.GetOperatorCorrelatedHealth(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to compute correlated health", err))
		return
	}
	writeJSON(w, http.StatusOK, health)
}

// ListCorrelatedAuditEvents is shared by both the tenant- and
// operator-scoped routes -- the underlying service call carries no scope
// parameter of its own because rbac.TxFromContext's transaction already has
// the right app.tenant_id/app.operator_id session GUC set by whichever
// route matched, and audit_events' own RLS policies do the actual scoping.
func (h *Handlers) ListCorrelatedAuditEvents(w http.ResponseWriter, r *http.Request) {
	resourceType := chi.URLParam(r, "resourceType")
	resourceID, err := uuid.Parse(chi.URLParam(r, "resourceID"))
	if err != nil || resourceType == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	out, err := h.svc.ListCorrelatedAuditEvents(r.Context(), resourceType, resourceID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list correlated audit events", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}
