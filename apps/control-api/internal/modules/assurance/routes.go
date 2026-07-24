package assurance

import (
	"github.com/go-chi/chi/v5"

	"gridkeep/control-api/internal/modules/rbac"
)

// MountTenantScoped registers onto a router already nested under
// /api/v1/enterprises/{tenantID} by app.go. Reads (SLOs, incidents, alert
// rules, alerts, correlated health) and the on-demand evaluate actions
// require only assurance.view; SLO/alert-rule configuration writes require
// the narrower slos.manage (deliberately reused for alert rules too --
// both are "reliability configuration" a workload owner sets, see
// migration 0033's header comment); incident lifecycle actions reuse the
// already-seeded incidents.view/incidents.manage from Milestone 1.
func MountTenantScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireEnterprisePermission("slos.manage")).Post("/slos", h.CreateSLO)
	r.With(authz.RequireEnterprisePermission("assurance.view")).Get("/slos", h.ListSLOs)
	r.With(authz.RequireEnterprisePermission("slos.manage")).Post("/slos/{sloID}/archive", h.ArchiveSLO)
	r.With(authz.RequireEnterprisePermission("assurance.view")).Post("/slos/{sloID}/evaluate", h.EvaluateSLO)
	r.With(authz.RequireEnterprisePermission("assurance.view")).Get("/slos/{sloID}/evaluations", h.ListSLOEvaluations)

	r.With(authz.RequireEnterprisePermission("incidents.manage")).Post("/incidents", h.CreateIncident)
	r.With(authz.RequireEnterprisePermission("incidents.view")).Get("/incidents", h.ListIncidents)
	r.With(authz.RequireEnterprisePermission("incidents.manage")).Post("/incidents/{incidentID}/acknowledge", h.AcknowledgeIncident)
	r.With(authz.RequireEnterprisePermission("incidents.manage")).Post("/incidents/{incidentID}/resolve", h.ResolveIncident)
	r.With(authz.RequireEnterprisePermission("incidents.view")).Get("/incidents/{incidentID}/events", h.ListIncidentEvents)

	r.With(authz.RequireEnterprisePermission("slos.manage")).Post("/alert-rules", h.CreateAlertRule)
	r.With(authz.RequireEnterprisePermission("assurance.view")).Get("/alert-rules", h.ListAlertRules)
	r.With(authz.RequireEnterprisePermission("slos.manage")).Post("/alert-rules/{ruleID}/status", h.SetAlertRuleStatus)
	r.With(authz.RequireEnterprisePermission("assurance.view")).Post("/alert-rules/{ruleID}/evaluate", h.EvaluateAlertRule)
	r.With(authz.RequireEnterprisePermission("assurance.view")).Get("/alerts", h.ListAlerts)

	r.With(authz.RequireEnterprisePermission("assurance.view")).Get("/health", h.GetCorrelatedHealth)
	r.With(authz.RequireEnterprisePermission("audit.view")).Get("/audit-correlation/{resourceType}/{resourceID}", h.ListCorrelatedAuditEvents)
}

// MountOperatorScoped registers onto a router already nested under
// /api/v1/operators/{operatorID} by app.go. Reads are available to any
// operator member (matching this codebase's established "view is
// membership, manage/mutate is a permission" convention); writes reuse
// operator.sla.manage (SLOs and alert rules) and operator.incidents.manage
// (incident lifecycle), both seeded in Milestone 1.
func MountOperatorScoped(r chi.Router, h *Handlers, authz *rbac.Middleware) {
	r.With(authz.RequireOperatorPermission("operator.sla.manage")).Post("/slos", h.CreateOperatorSLO)
	r.With(authz.RequireOperatorMembership()).Get("/slos", h.ListOperatorSLOs)
	r.With(authz.RequireOperatorPermission("operator.sla.manage")).Post("/slos/{sloID}/archive", h.ArchiveOperatorSLO)
	r.With(authz.RequireOperatorMembership()).Post("/slos/{sloID}/evaluate", h.EvaluateOperatorSLO)
	r.With(authz.RequireOperatorMembership()).Get("/slos/{sloID}/evaluations", h.ListOperatorSLOEvaluations)

	r.With(authz.RequireOperatorPermission("operator.incidents.manage")).Post("/incidents", h.CreateOperatorIncident)
	r.With(authz.RequireOperatorMembership()).Get("/incidents", h.ListOperatorIncidents)
	r.With(authz.RequireOperatorPermission("operator.incidents.manage")).Post("/incidents/{incidentID}/acknowledge", h.AcknowledgeOperatorIncident)
	r.With(authz.RequireOperatorPermission("operator.incidents.manage")).Post("/incidents/{incidentID}/resolve", h.ResolveOperatorIncident)
	r.With(authz.RequireOperatorMembership()).Get("/incidents/{incidentID}/events", h.ListOperatorIncidentEvents)

	r.With(authz.RequireOperatorPermission("operator.sla.manage")).Post("/alert-rules", h.CreateOperatorAlertRule)
	r.With(authz.RequireOperatorMembership()).Get("/alert-rules", h.ListOperatorAlertRules)
	r.With(authz.RequireOperatorPermission("operator.sla.manage")).Post("/alert-rules/{ruleID}/status", h.SetOperatorAlertRuleStatus)
	r.With(authz.RequireOperatorMembership()).Post("/alert-rules/{ruleID}/evaluate", h.EvaluateOperatorAlertRule)
	r.With(authz.RequireOperatorMembership()).Get("/alerts", h.ListOperatorAlerts)

	r.With(authz.RequireOperatorMembership()).Get("/health", h.GetOperatorCorrelatedHealth)
	r.With(authz.RequireOperatorPermission("operator.audit.view")).Get("/audit-correlation/{resourceType}/{resourceID}", h.ListCorrelatedAuditEvents)
}
