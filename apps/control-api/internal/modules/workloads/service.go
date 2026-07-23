package workloads

import (
	"context"
	"errors"
	"fmt"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
)

var (
	ErrWorkloadNotFound        = errors.New("workload not found")
	ErrWorkloadKeyExists       = errors.New("a workload with this key already exists")
	ErrVersionNotFound         = errors.New("workload version not found")
	ErrNotADraft               = errors.New("workload version is not in draft status")
	ErrNotPendingPublish       = errors.New("workload version is not pending publish")
	ErrCannotSelfApprove       = errors.New("the same user cannot both request and approve a workload version publish")
	ErrNotPublished            = errors.New("workload version is not published")
	ErrImageNotApproved        = errors.New("the referenced container image is not approved and cannot be selected")
	ErrModelVersionNotApproved = errors.New("the referenced model version is not approved and cannot be selected")
	ErrModelGeographyMismatch  = errors.New("the workload's residency requirements are incompatible with the selected model version's geographic restrictions")
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

func (s *Service) ListWorkloads(ctx context.Context) ([]Workload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listWorkloads(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) GetWorkload(ctx context.Context, id uuid.UUID) (Workload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	w, exists, err := getWorkloadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Workload{}, err
	}
	if !exists {
		return Workload{}, ErrWorkloadNotFound
	}
	return w, nil
}

func (s *Service) CreateWorkload(ctx context.Context, workloadKey, workloadType, name, description string) (Workload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getWorkloadByKey(ctx, scopedTx.Tx, *scope.TenantID, workloadKey); err != nil {
		return Workload{}, err
	} else if exists {
		return Workload{}, ErrWorkloadKeyExists
	}

	w, err := createWorkload(ctx, scopedTx.Tx, *scope.TenantID, workloadKey, workloadType, name, description, actor)
	if err != nil {
		return Workload{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.created", TargetType: "workload", TargetID: &w.ID,
		Evidence: map[string]any{"workload_key": workloadKey, "workload_type": workloadType},
	}); err != nil {
		return Workload{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Workload{}, err
	}
	return w, nil
}

func (s *Service) RetireWorkload(ctx context.Context, id uuid.UUID) (Workload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markWorkloadRetired(ctx, scopedTx.Tx, id)
	if err != nil {
		return Workload{}, err
	}
	if !ok {
		return Workload{}, ErrWorkloadNotFound
	}
	w, exists, err := getWorkloadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Workload{}, err
	}
	if !exists {
		return Workload{}, ErrWorkloadNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.retired", TargetType: "workload", TargetID: &id,
	}); err != nil {
		return Workload{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Workload{}, err
	}
	return w, nil
}

// validateSelections enforces that a container image can only be selected
// while 'approved' and a model version only while 'approved', and that the
// workload's declared residency requirements are compatible with the
// selected model version's permitted/prohibited geographies -- this is
// where "retired or revoked images/models cannot be selected for new
// workload versions" and "model licences and geographic restrictions are
// enforced" are actually implemented, not just documented.
func (s *Service) validateSelections(ctx context.Context, tx conn, tenantID uuid.UUID, in VersionInput) error {
	if in.ContainerImageID != nil {
		approved, err := imageIsApproved(ctx, tx, tenantID, *in.ContainerImageID)
		if err != nil {
			return err
		}
		if !approved {
			return ErrImageNotApproved
		}
	}
	if in.ModelVersionID != nil {
		status, permitted, prohibited, err := modelVersionApprovalAndGeography(ctx, tx, tenantID, *in.ModelVersionID)
		if err != nil {
			return err
		}
		if status != "approved" {
			return ErrModelVersionNotApproved
		}
		if err := validateGeography(in.ResidencyRequirements, permitted, prohibited); err != nil {
			return err
		}
	}
	return nil
}

func validateGeography(residency map[string]any, permitted, prohibited []string) error {
	allowedCountries := extractStringSlice(residency, "allowed_countries")
	if len(allowedCountries) == 0 {
		return nil
	}
	prohibitedSet := toSet(prohibited)
	permittedSet := toSet(permitted)
	for _, country := range allowedCountries {
		if prohibitedSet[country] {
			return fmt.Errorf("%w: %q is prohibited", ErrModelGeographyMismatch, country)
		}
		if len(permittedSet) > 0 && !permittedSet[country] {
			return fmt.Errorf("%w: %q is not permitted", ErrModelGeographyMismatch, country)
		}
	}
	return nil
}

func extractStringSlice(m map[string]any, key string) []string {
	raw, ok := m[key]
	if !ok {
		return nil
	}
	arr, ok := raw.([]any)
	if !ok {
		return nil
	}
	out := make([]string, 0, len(arr))
	for _, v := range arr {
		if str, ok := v.(string); ok {
			out = append(out, str)
		}
	}
	return out
}

func toSet(items []string) map[string]bool {
	set := make(map[string]bool, len(items))
	for _, item := range items {
		set[item] = true
	}
	return set
}

func (s *Service) ListVersions(ctx context.Context, workloadID uuid.UUID) ([]WorkloadVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listVersions(ctx, scopedTx.Tx, *scope.TenantID, workloadID)
}

func (s *Service) GetVersion(ctx context.Context, id uuid.UUID) (WorkloadVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	v, exists, err := getVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !exists {
		return WorkloadVersion{}, ErrVersionNotFound
	}
	return v, nil
}

func (s *Service) CreateDraftVersion(ctx context.Context, workloadID uuid.UUID, in VersionInput) (WorkloadVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getWorkloadByID(ctx, scopedTx.Tx, *scope.TenantID, workloadID); err != nil {
		return WorkloadVersion{}, err
	} else if !exists {
		return WorkloadVersion{}, ErrWorkloadNotFound
	}
	if err := s.validateSelections(ctx, scopedTx.Tx, *scope.TenantID, in); err != nil {
		return WorkloadVersion{}, err
	}

	v, err := createVersionDraft(ctx, scopedTx.Tx, *scope.TenantID, workloadID, actor, in)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.version_drafted", TargetType: "workload_version", TargetID: &v.ID,
		Evidence: map[string]any{"workload_id": workloadID, "version": v.Version},
	}); err != nil {
		return WorkloadVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return WorkloadVersion{}, err
	}
	return v, nil
}

func (s *Service) EditDraftVersion(ctx context.Context, id uuid.UUID, in VersionInput) (WorkloadVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if err := s.validateSelections(ctx, scopedTx.Tx, *scope.TenantID, in); err != nil {
		return WorkloadVersion{}, err
	}

	ok, err := updateVersionDraft(ctx, scopedTx.Tx, id, in)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !ok {
		return WorkloadVersion{}, ErrNotADraft
	}
	v, exists, err := getVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !exists {
		return WorkloadVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.version_edited", TargetType: "workload_version", TargetID: &id,
	}); err != nil {
		return WorkloadVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return WorkloadVersion{}, err
	}
	return v, nil
}

func (s *Service) RequestPublish(ctx context.Context, id uuid.UUID) (WorkloadVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markRequestedPublish(ctx, scopedTx.Tx, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !ok {
		return WorkloadVersion{}, ErrNotADraft
	}
	v, exists, err := getVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !exists {
		return WorkloadVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.publish_requested", TargetType: "workload_version", TargetID: &id,
	}); err != nil {
		return WorkloadVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return WorkloadVersion{}, err
	}
	return v, nil
}

// ApprovePublish is dual control: a genuinely different user than whoever
// called RequestPublish, enforced both here and by the
// workload_versions_no_self_approval DB CHECK constraint. Publication makes
// the version immutable (see the workload_versions_immutability trigger).
func (s *Service) ApprovePublish(ctx context.Context, id uuid.UUID) (WorkloadVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	v, exists, err := getVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !exists {
		return WorkloadVersion{}, ErrVersionNotFound
	}
	if v.Status != "pending_publish" {
		return WorkloadVersion{}, ErrNotPendingPublish
	}
	if v.RequestedBy == actor {
		return WorkloadVersion{}, ErrCannotSelfApprove
	}

	ok, err := markPublished(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !ok {
		return WorkloadVersion{}, ErrNotPendingPublish
	}
	published, exists, err := getVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !exists {
		return WorkloadVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.version_published", TargetType: "workload_version", TargetID: &id,
		Evidence: map[string]any{"requested_by": v.RequestedBy},
	}); err != nil {
		return WorkloadVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return WorkloadVersion{}, err
	}
	return published, nil
}

func (s *Service) DeprecateVersion(ctx context.Context, id uuid.UUID) (WorkloadVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markDeprecated(ctx, scopedTx.Tx, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !ok {
		return WorkloadVersion{}, ErrNotPublished
	}
	v, exists, err := getVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !exists {
		return WorkloadVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.version_deprecated", TargetType: "workload_version", TargetID: &id,
	}); err != nil {
		return WorkloadVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return WorkloadVersion{}, err
	}
	return v, nil
}

func (s *Service) RetireVersion(ctx context.Context, id uuid.UUID, reason string) (WorkloadVersion, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markVersionRetired(ctx, scopedTx.Tx, id, reason)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !ok {
		return WorkloadVersion{}, ErrNotPublished
	}
	v, exists, err := getVersionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return WorkloadVersion{}, err
	}
	if !exists {
		return WorkloadVersion{}, ErrVersionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.version_retired", TargetType: "workload_version", TargetID: &id,
		Evidence: map[string]any{"reason": reason},
	}); err != nil {
		return WorkloadVersion{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return WorkloadVersion{}, err
	}
	return v, nil
}

func (s *Service) AddComponent(ctx context.Context, versionID, containerImageID uuid.UUID, componentKey, name string, command, args []string, env map[string]any, isPrimary bool) (Component, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	approved, err := imageIsApproved(ctx, scopedTx.Tx, *scope.TenantID, containerImageID)
	if err != nil {
		return Component{}, err
	}
	if !approved {
		return Component{}, ErrImageNotApproved
	}

	comp, err := createComponent(ctx, scopedTx.Tx, *scope.TenantID, versionID, containerImageID, componentKey, name, command, args, env, isPrimary)
	if err != nil {
		return Component{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.component_added", TargetType: "workload_version", TargetID: &versionID,
		Evidence: map[string]any{"component_key": componentKey},
	}); err != nil {
		return Component{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Component{}, err
	}
	return comp, nil
}

func (s *Service) ListComponents(ctx context.Context, versionID uuid.UUID) ([]Component, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listComponents(ctx, scopedTx.Tx, *scope.TenantID, versionID)
}

func (s *Service) AddHealthCheck(ctx context.Context, componentID uuid.UUID, checkType, path string, port *int, command []string, intervalSeconds, timeoutSeconds, failureThreshold int) (HealthCheck, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	hc, err := createHealthCheck(ctx, scopedTx.Tx, *scope.TenantID, componentID, checkType, path, port, command, intervalSeconds, timeoutSeconds, failureThreshold)
	if err != nil {
		return HealthCheck{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.health_check_added", TargetType: "workload_component", TargetID: &componentID,
		Evidence: map[string]any{"check_type": checkType},
	}); err != nil {
		return HealthCheck{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return HealthCheck{}, err
	}
	return hc, nil
}

func (s *Service) ListHealthChecks(ctx context.Context, componentID uuid.UUID) ([]HealthCheck, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listHealthChecks(ctx, scopedTx.Tx, *scope.TenantID, componentID)
}

func (s *Service) LinkArtefact(ctx context.Context, versionID, artefactUploadID uuid.UUID, role string) (ArtefactLink, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	link, err := linkArtefact(ctx, scopedTx.Tx, *scope.TenantID, versionID, artefactUploadID, role)
	if err != nil {
		return ArtefactLink{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.artefact_linked", TargetType: "workload_version", TargetID: &versionID,
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
	return listArtefactLinks(ctx, scopedTx.Tx, *scope.TenantID, versionID)
}

func (s *Service) LinkSBOM(ctx context.Context, versionID, sbomID uuid.UUID) (SBOMLink, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	link, err := linkSBOM(ctx, scopedTx.Tx, *scope.TenantID, versionID, sbomID)
	if err != nil {
		return SBOMLink{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "workloads.sbom_linked", TargetType: "workload_version", TargetID: &versionID,
	}); err != nil {
		return SBOMLink{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SBOMLink{}, err
	}
	return link, nil
}

func (s *Service) ListSBOMLinks(ctx context.Context, versionID uuid.UUID) ([]SBOMLink, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listSBOMLinks(ctx, scopedTx.Tx, *scope.TenantID, versionID)
}
