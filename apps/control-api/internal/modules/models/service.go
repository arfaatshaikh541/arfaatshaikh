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
	ErrModelNotFound        = errors.New("model not found")
	ErrModelKeyExists       = errors.New("a model with this key already exists")
	ErrVersionNotFound      = errors.New("model version not found")
	ErrNotADraft            = errors.New("model version is not in draft status")
	ErrNotPendingApproval   = errors.New("model version is not pending approval")
	ErrCannotSelfApprove    = errors.New("the same user cannot both request and approve a model version")
	ErrNotApproved          = errors.New("model version is not approved")
	ErrNotApprovedOrRetired = errors.New("model version is not approved or retired")
	ErrLicenceNotFound      = errors.New("licence not found")
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

func (s *Service) ListProviders(ctx context.Context) ([]Provider, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listProviders(ctx, scopedTx.Tx)
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
