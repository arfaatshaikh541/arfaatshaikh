package models

import (
	"context"
	"errors"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
)

var (
	ErrModelNotFound            = errors.New("model not found")
	ErrModelKeyExists           = errors.New("a model with this key already exists")
	ErrVersionNotFound          = errors.New("model version not found")
	ErrNotADraft                = errors.New("model version is not in draft status")
	ErrNotPendingApproval       = errors.New("model version is not pending approval")
	ErrCannotSelfApprove        = errors.New("the same user cannot both request and approve a model version")
	ErrNotApproved              = errors.New("model version is not approved")
	ErrNotApprovedOrRetired     = errors.New("model version is not approved or retired")
	ErrLicenceNotFound          = errors.New("licence not found")
	ErrLicenceForbidsCommercial = errors.New("the model version's licence does not allow commercial use and cannot be published or granted")
	ErrNotPublishable           = errors.New("model version must be approved before it can be published")
	ErrNotPublished             = errors.New("model version is not currently published")
	ErrGrantNotFound            = errors.New("model access grant not found")
	ErrProviderKeyExists        = errors.New("a model provider with this key already exists")
	ErrProviderNotFound         = errors.New("model provider not found")
	ErrProviderNotActive        = errors.New("model provider is not active")
	ErrProviderNotSuspended     = errors.New("model provider is not suspended")
)

type Service struct {
	store *dbpkg.Store
}

func NewService(store *dbpkg.Store) *Service {
	return &Service{store: store}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

// ListProviders reads directly off the pool, not a scoped transaction --
// model_providers carries no RLS at all (it is platform-curated global
// reference data, the same role jurisdictions/regions play), and this
// method is now called from both a tenant-scoped route (which has an rbac-
// wrapped context) and Milestone 15's top-level, auth-only route (which does
// not), the same "reads require only an authenticated session" pattern
// registry.Service.ListJurisdictions/ListRegions already use for the
// identical reason.
func (s *Service) ListProviders(ctx context.Context) ([]Provider, error) {
	return listProviders(ctx, s.store.Pool)
}

func (s *Service) ListLicences(ctx context.Context) ([]Licence, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listLicences(ctx, scopedTx.Tx)
}

func (s *Service) ListModels(ctx context.Context) ([]Model, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listModels(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) GetModel(ctx context.Context, id uuid.UUID) (Model, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	m, exists, err := getModelByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Model{}, err
	}
	if !exists {
		return Model{}, ErrModelNotFound
	}
	return m, nil
}

func (s *Service) CreateModel(ctx context.Context, modelKey, name, description string, providerID *uuid.UUID) (Model, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getModelByKey(ctx, scopedTx.Tx, *scope.TenantID, modelKey); err != nil {
		return Model{}, err
	} else if exists {
		return Model{}, ErrModelKeyExists
	}

	m, err := createModel(ctx, scopedTx.Tx, *scope.TenantID, modelKey, name, description, providerID)
	if err != nil {
		return Model{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "models.registered",
		TargetType:  "model",
		TargetID:    &m.ID,
		Evidence:    map[string]any{"model_key": modelKey, "name": name},
	}); err != nil {
		return Model{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Model{}, err
	}
	return m, nil
}

func (s *Service) ListVersions(ctx context.Context, modelID uuid.UUID) ([]ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listModelVersions(ctx, scopedTx.Tx, *scope.TenantID, modelID)
}

func (s *Service) GetVersion(ctx context.Context, id uuid.UUID) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	return v, nil
}

func (s *Service) CreateDraftVersion(ctx context.Context, modelID uuid.UUID, in ModelVersionInput) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getModelByID(ctx, scopedTx.Tx, *scope.TenantID, modelID); err != nil {
		return ModelVersion{}, err
	} else if !exists {
		return ModelVersion{}, ErrModelNotFound
	}
	if _, exists, err := getLicenceByID(ctx, scopedTx.Tx, in.LicenceID); err != nil {
		return ModelVersion{}, err
	} else if !exists {
		return ModelVersion{}, ErrLicenceNotFound
	}

	v, err := createModelVersionDraft(ctx, scopedTx.Tx, *scope.TenantID, modelID, actor, in)
	if err != nil {
		return ModelVersion{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "models.version_drafted",
		TargetType:  "model_version",
		TargetID:    &v.ID,
		Evidence:    map[string]any{"model_id": modelID, "version": v.Version},
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return v, nil
}

func (s *Service) EditDraftVersion(ctx context.Context, id uuid.UUID, in ModelVersionInput) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getLicenceByID(ctx, scopedTx.Tx, in.LicenceID); err != nil {
		return ModelVersion{}, err
	} else if !exists {
		return ModelVersion{}, ErrLicenceNotFound
	}

	ok, err := updateModelVersionDraft(ctx, scopedTx.Tx, id, in)
	if err != nil {
		return ModelVersion{}, err
	}
	if !ok {
		return ModelVersion{}, ErrNotADraft
	}
	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "models.version_edited",
		TargetType:  "model_version",
		TargetID:    &id,
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return v, nil
}

func (s *Service) RequestApproval(ctx context.Context, id uuid.UUID) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markRequestedApproval(ctx, scopedTx.Tx, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !ok {
		return ModelVersion{}, ErrNotADraft
	}
	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "models.approval_requested",
		TargetType:  "model_version",
		TargetID:    &id,
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return v, nil
}

// ApproveVersion is dual control: a genuinely different user than whoever
// called RequestApproval, enforced both here and by the
// model_versions_no_self_approval DB CHECK constraint.
func (s *Service) ApproveVersion(ctx context.Context, id uuid.UUID) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if v.Status != "pending_approval" {
		return ModelVersion{}, ErrNotPendingApproval
	}
	if v.RequestedBy == actor {
		return ModelVersion{}, ErrCannotSelfApprove
	}

	ok, err := markApproved(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return ModelVersion{}, err
	}
	if !ok {
		return ModelVersion{}, ErrNotPendingApproval
	}
	approved, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "models.version_approved",
		TargetType:  "model_version",
		TargetID:    &id,
		Evidence:    map[string]any{"requested_by": v.RequestedBy},
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return approved, nil
}

func (s *Service) RejectVersion(ctx context.Context, id uuid.UUID, reason string) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markRejected(ctx, scopedTx.Tx, id, reason)
	if err != nil {
		return ModelVersion{}, err
	}
	if !ok {
		return ModelVersion{}, ErrNotPendingApproval
	}
	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "models.version_rejected",
		TargetType:  "model_version",
		TargetID:    &id,
		Evidence:    map[string]any{"reason": reason},
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return v, nil
}

func (s *Service) RetireVersion(ctx context.Context, id uuid.UUID, reason string) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markRetired(ctx, scopedTx.Tx, id, reason)
	if err != nil {
		return ModelVersion{}, err
	}
	if !ok {
		return ModelVersion{}, ErrNotApproved
	}
	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "models.version_retired",
		TargetType:  "model_version",
		TargetID:    &id,
		Evidence:    map[string]any{"reason": reason},
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return v, nil
}

// RevokeVersion is the emergency, "untrust immediately" counterpart to
// RetireVersion -- applicable to a version that is currently approved OR
// already retired (e.g. a legal/security issue discovered after the model
// was already retired for ordinary end-of-life reasons).
func (s *Service) RevokeVersion(ctx context.Context, id uuid.UUID, reason string) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markRevoked(ctx, scopedTx.Tx, id, reason)
	if err != nil {
		return ModelVersion{}, err
	}
	if !ok {
		return ModelVersion{}, ErrNotApprovedOrRetired
	}
	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "models.version_revoked",
		TargetType:  "model_version",
		TargetID:    &id,
		Evidence:    map[string]any{"reason": reason},
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return v, nil
}

func (s *Service) AddCapability(ctx context.Context, versionID uuid.UUID, capabilityKey, description string) (Capability, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	capability, err := createCapability(ctx, scopedTx.Tx, *scope.TenantID, versionID, capabilityKey, description)
	if err != nil {
		return Capability{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.capability_added", TargetType: "model_version", TargetID: &versionID,
		Evidence: map[string]any{"capability_key": capabilityKey},
	}); err != nil {
		return Capability{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Capability{}, err
	}
	return capability, nil
}

func (s *Service) ListCapabilities(ctx context.Context, versionID uuid.UUID) ([]Capability, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listCapabilities(ctx, scopedTx.Tx, *scope.TenantID, versionID)
}

func (s *Service) AddBenchmark(ctx context.Context, versionID uuid.UUID, benchmarkName, metricName string, metricValue float64, evaluatedAt time.Time) (Benchmark, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	b, err := createBenchmark(ctx, scopedTx.Tx, *scope.TenantID, versionID, benchmarkName, metricName, metricValue, evaluatedAt)
	if err != nil {
		return Benchmark{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.benchmark_added", TargetType: "model_version", TargetID: &versionID,
		Evidence: map[string]any{"benchmark_name": benchmarkName, "metric_name": metricName, "metric_value": metricValue},
	}); err != nil {
		return Benchmark{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Benchmark{}, err
	}
	return b, nil
}

func (s *Service) ListBenchmarks(ctx context.Context, versionID uuid.UUID) ([]Benchmark, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listBenchmarks(ctx, scopedTx.Tx, *scope.TenantID, versionID)
}

func (s *Service) AddSafetyEvaluation(ctx context.Context, versionID uuid.UUID, evaluator, methodology, result string, findings map[string]any, evaluatedAt time.Time) (SafetyEvaluation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	se, err := createSafetyEvaluation(ctx, scopedTx.Tx, *scope.TenantID, versionID, evaluator, methodology, result, findings, evaluatedAt)
	if err != nil {
		return SafetyEvaluation{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.safety_evaluation_added", TargetType: "model_version", TargetID: &versionID,
		Evidence: map[string]any{"evaluator": evaluator, "result": result},
	}); err != nil {
		return SafetyEvaluation{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SafetyEvaluation{}, err
	}
	return se, nil
}

func (s *Service) ListSafetyEvaluations(ctx context.Context, versionID uuid.UUID) ([]SafetyEvaluation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listSafetyEvaluations(ctx, scopedTx.Tx, *scope.TenantID, versionID)
}

func (s *Service) AddDeploymentProfile(ctx context.Context, versionID uuid.UUID, profileKey, name string, resourceRequirements map[string]any) (DeploymentProfile, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	p, err := createDeploymentProfile(ctx, scopedTx.Tx, *scope.TenantID, versionID, profileKey, name, resourceRequirements)
	if err != nil {
		return DeploymentProfile{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.deployment_profile_added", TargetType: "model_version", TargetID: &versionID,
		Evidence: map[string]any{"profile_key": profileKey},
	}); err != nil {
		return DeploymentProfile{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return DeploymentProfile{}, err
	}
	return p, nil
}

func (s *Service) ListDeploymentProfiles(ctx context.Context, versionID uuid.UUID) ([]DeploymentProfile, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listDeploymentProfiles(ctx, scopedTx.Tx, *scope.TenantID, versionID)
}

func (s *Service) LinkArtefact(ctx context.Context, versionID, artefactUploadID uuid.UUID, role, checksum string) (ArtefactLink, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	link, err := linkModelArtefact(ctx, scopedTx.Tx, *scope.TenantID, versionID, artefactUploadID, role, checksum)
	if err != nil {
		return ArtefactLink{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.artefact_linked", TargetType: "model_version", TargetID: &versionID,
	}); err != nil {
		return ArtefactLink{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ArtefactLink{}, err
	}
	return link, nil
}

func (s *Service) ListArtefactLinks(ctx context.Context, versionID uuid.UUID) ([]ArtefactLink, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listModelArtefacts(ctx, scopedTx.Tx, *scope.TenantID, versionID)
}

// ---------------------------------------------------------------------
// marketplace (Milestone 13: AI Model Exchange)
// ---------------------------------------------------------------------

// requireCommercialUseLicence loads the version's own tenant-scoped record to
// find its licence, then enforces that the licence actually allows
// commercial use before permitting the version to be published or granted --
// this is what turns AllowsCommercialUse from stored metadata (Milestone 4)
// into a fail-closed rule (Milestone 13's "model licensing" requirement).
func (s *Service) requireCommercialUseLicence(ctx context.Context, tx conn, tenantID, versionID uuid.UUID) (ModelVersion, error) {
	v, exists, err := getModelVersionByID(ctx, tx, tenantID, versionID)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	licence, exists, err := getLicenceByID(ctx, tx, v.LicenceID)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrLicenceNotFound
	}
	if !licence.AllowsCommercialUse {
		return ModelVersion{}, ErrLicenceForbidsCommercial
	}
	return v, nil
}

// PublishVersion lists an approved model version on the exchange: visible to
// every tenant if public, or only to tenants holding an active access grant
// if left private (a grant can still be issued either way -- see
// CreateAccessGrant). Price is set here rather than via EditDraftVersion
// because listing/pricing is a marketplace concern, not one of the frozen
// technical facts a draft edit governs.
func (s *Service) PublishVersion(ctx context.Context, id uuid.UUID, pricePerUnit *float64, pricingUnit, currency string) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, err := s.requireCommercialUseLicence(ctx, scopedTx.Tx, *scope.TenantID, id); err != nil {
		return ModelVersion{}, err
	}

	ok, err := publishModelVersion(ctx, scopedTx.Tx, id, pricePerUnit, pricingUnit, currency)
	if err != nil {
		return ModelVersion{}, err
	}
	if !ok {
		return ModelVersion{}, ErrNotPublishable
	}
	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.version_published", TargetType: "model_version", TargetID: &id,
		Evidence: map[string]any{"price_per_unit": pricePerUnit, "pricing_unit": pricingUnit, "currency": currency},
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return v, nil
}

func (s *Service) UnpublishVersion(ctx context.Context, id uuid.UUID) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := unpublishModelVersion(ctx, scopedTx.Tx, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !ok {
		return ModelVersion{}, ErrNotPublished
	}
	v, exists, err := getModelVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.version_unpublished", TargetType: "model_version", TargetID: &id,
	}); err != nil {
		return ModelVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelVersion{}, err
	}
	return v, nil
}

// CreateAccessGrant is the owning tenant inviting one specific other tenant
// to select this model version (required for a private version; optional,
// price-override-only, for a public one) -- the same shape and same
// commercial-use-licence gate as PublishVersion.
func (s *Service) CreateAccessGrant(ctx context.Context, versionID uuid.UUID, in CreateAccessGrantInput) (ModelAccessGrant, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, err := s.requireCommercialUseLicence(ctx, scopedTx.Tx, *scope.TenantID, versionID); err != nil {
		return ModelAccessGrant{}, err
	}

	g, err := createAccessGrant(ctx, scopedTx.Tx, versionID, *scope.TenantID, in.GranteeTenantID, actor, in.PricePerUnitOverride)
	if err != nil {
		return ModelAccessGrant{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.access_granted", TargetType: "model_version", TargetID: &versionID,
		Evidence: map[string]any{"grantee_tenant_id": in.GranteeTenantID, "price_per_unit_override": in.PricePerUnitOverride},
	}); err != nil {
		return ModelAccessGrant{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ModelAccessGrant{}, err
	}
	return g, nil
}

func (s *Service) ListAccessGrantsForVersion(ctx context.Context, versionID uuid.UUID) ([]ModelAccessGrant, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAccessGrantsForVersion(ctx, scopedTx.Tx, versionID)
}

// ListMyModelAccessGrants is the grantee side: the tenants I've been given
// access to another tenant's model versions through.
func (s *Service) ListMyModelAccessGrants(ctx context.Context) ([]ModelAccessGrant, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listReceivedAccessGrants(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) RevokeAccessGrant(ctx context.Context, id uuid.UUID) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	scope, _ := rbac.FromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := revokeAccessGrant(ctx, scopedTx.Tx, id)
	if err != nil {
		return err
	}
	if !ok {
		return ErrGrantNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "models.access_revoked", TargetType: "model_access_grant", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// ListMarketplaceModelVersions browses other tenants' published model
// versions, decorating each with this tenant's own contracted price (an
// active grant's override, if any) in place of the public base price -- the
// same "resolve the override once, return it in the row" discipline
// internal/modules/placement.EvaluatePlacement already established in
// Milestone 12, so the frontend never has to reconcile two numbers itself.
func (s *Service) ListMarketplaceModelVersions(ctx context.Context) ([]ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	versions, err := listMarketplaceModelVersions(ctx, scopedTx.Tx, *scope.TenantID)
	if err != nil {
		return nil, err
	}
	for i := range versions {
		override, err := activeGrantPriceOverride(ctx, scopedTx.Tx, versions[i].ID, *scope.TenantID)
		if err != nil {
			return nil, err
		}
		if override != nil {
			versions[i].PricePerUnit = override
		}
	}
	return versions, nil
}

func (s *Service) GetMarketplaceModelVersion(ctx context.Context, id uuid.UUID) (ModelVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	v, exists, err := getMarketplaceModelVersion(ctx, scopedTx.Tx, id)
	if err != nil {
		return ModelVersion{}, err
	}
	if !exists {
		return ModelVersion{}, ErrVersionNotFound
	}
	if override, err := activeGrantPriceOverride(ctx, scopedTx.Tx, id, *scope.TenantID); err != nil {
		return ModelVersion{}, err
	} else if override != nil {
		v.PricePerUnit = override
	}
	return v, nil
}

func (s *Service) ListMarketplaceCapabilities(ctx context.Context, versionID uuid.UUID) ([]Capability, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listMarketplaceCapabilities(ctx, scopedTx.Tx, versionID)
}

func (s *Service) ListMarketplaceBenchmarks(ctx context.Context, versionID uuid.UUID) ([]Benchmark, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listMarketplaceBenchmarks(ctx, scopedTx.Tx, versionID)
}

func (s *Service) ListMarketplaceSafetyEvaluations(ctx context.Context, versionID uuid.UUID) ([]SafetyEvaluation, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listMarketplaceSafetyEvaluations(ctx, scopedTx.Tx, versionID)
}

func (s *Service) ListMarketplaceDeploymentProfiles(ctx context.Context, versionID uuid.UUID) ([]DeploymentProfile, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listMarketplaceDeploymentProfiles(ctx, scopedTx.Tx, versionID)
}

// ---------------------------------------------------------------------
// provider onboarding (Milestone 13)
// ---------------------------------------------------------------------

func (s *Service) CreateProvider(ctx context.Context, in CreateProviderInput) (Provider, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getProviderByKey(ctx, scopedTx.Tx, in.Key); err != nil {
		return Provider{}, err
	} else if exists {
		return Provider{}, ErrProviderKeyExists
	}

	p, err := createProvider(ctx, scopedTx.Tx, in.Key, in.Name, in.Website, actor)
	if err != nil {
		return Provider{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopePlatform,
		Action: "models.provider_onboarded", TargetType: "model_provider", TargetID: &p.ID,
		Evidence: map[string]any{"key": in.Key, "name": in.Name},
	}); err != nil {
		return Provider{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Provider{}, err
	}
	return p, nil
}

func (s *Service) SuspendProvider(ctx context.Context, id uuid.UUID) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := setProviderStatus(ctx, scopedTx.Tx, id, "suspended", "active")
	if err != nil {
		return err
	}
	if !ok {
		return ErrProviderNotActive
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopePlatform,
		Action: "models.provider_suspended", TargetType: "model_provider", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) ReactivateProvider(ctx context.Context, id uuid.UUID) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := setProviderStatus(ctx, scopedTx.Tx, id, "active", "suspended")
	if err != nil {
		return err
	}
	if !ok {
		return ErrProviderNotSuspended
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopePlatform,
		Action: "models.provider_reactivated", TargetType: "model_provider", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}
