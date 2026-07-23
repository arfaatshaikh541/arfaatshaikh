package policies

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/policyengine"
)

var (
	ErrPolicyNotFound           = errors.New("policy not found")
	ErrDraftAlreadyExists       = errors.New("a draft already exists for this policy key")
	ErrNotADraft                = errors.New("policy is not in draft status")
	ErrNotPendingPublish        = errors.New("policy is not pending publish")
	ErrCannotSelfApprove        = errors.New("the same user cannot both request and approve a publish")
	ErrPolicyNotPublished       = errors.New("policy is not published")
	ErrPublishBlockedByConflict = errors.New("publish blocked: this policy conflicts with another published policy")
)

type Config struct {
	PolicyEngineTimeout time.Duration
}

type Service struct {
	store        *dbpkg.Store
	policyEngine *policyengine.Client
	cfg          Config
}

func NewService(store *dbpkg.Store, policyEngineClient *policyengine.Client, cfg Config) *Service {
	return &Service{store: store, policyEngine: policyEngineClient, cfg: cfg}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

func (s *Service) ListPolicies(ctx context.Context) ([]SovereigntyPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listLatestVersionPerKey(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListVersions(ctx context.Context, policyKey string) ([]SovereigntyPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listVersionsByKey(ctx, scopedTx.Tx, *scope.TenantID, policyKey)
}

func (s *Service) GetPolicy(ctx context.Context, id uuid.UUID) (SovereigntyPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	p, ok, err := getPolicyByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if !ok {
		return SovereigntyPolicy{}, ErrPolicyNotFound
	}
	return p, nil
}

func (s *Service) CreateDraft(ctx context.Context, policyKey, name string, document policyengine.PolicyDocument) (SovereigntyPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getDraftByKey(ctx, scopedTx.Tx, *scope.TenantID, policyKey); err != nil {
		return SovereigntyPolicy{}, err
	} else if exists {
		return SovereigntyPolicy{}, ErrDraftAlreadyExists
	}

	p, err := createDraft(ctx, scopedTx.Tx, *scope.TenantID, policyKey, name, document, actor, nil)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "policies.draft_created",
		TargetType:  "sovereignty_policy",
		TargetID:    &p.ID,
		Evidence:    map[string]any{"policy_key": policyKey, "version": p.Version, "name": name},
	}); err != nil {
		return SovereigntyPolicy{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SovereigntyPolicy{}, err
	}
	return p, nil
}

func (s *Service) EditDraft(ctx context.Context, id uuid.UUID, name string, document policyengine.PolicyDocument) (SovereigntyPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := updateDraftDocument(ctx, scopedTx.Tx, id, name, document)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if !ok {
		return SovereigntyPolicy{}, ErrNotADraft
	}
	p, exists, err := getPolicyByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if !exists {
		return SovereigntyPolicy{}, ErrPolicyNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "policies.draft_edited",
		TargetType:  "sovereignty_policy",
		TargetID:    &id,
		Evidence:    map[string]any{"policy_key": p.PolicyKey, "version": p.Version},
	}); err != nil {
		return SovereigntyPolicy{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SovereigntyPolicy{}, err
	}
	return p, nil
}

// RequestPublish moves a draft to pending_publish -- the "author" half of
// dual control. It does not itself make the policy live; ApprovePublish
// (by a different user) does.
func (s *Service) RequestPublish(ctx context.Context, id uuid.UUID) (SovereigntyPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markRequestedPublish(ctx, scopedTx.Tx, id)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if !ok {
		return SovereigntyPolicy{}, ErrNotADraft
	}
	p, exists, err := getPolicyByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if !exists {
		return SovereigntyPolicy{}, ErrPolicyNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "policies.publish_requested",
		TargetType:  "sovereignty_policy",
		TargetID:    &id,
		Evidence:    map[string]any{"policy_key": p.PolicyKey, "version": p.Version},
	}); err != nil {
		return SovereigntyPolicy{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SovereigntyPolicy{}, err
	}
	return p, nil
}

// ApprovePublish is the "approver" half of dual control: a genuinely
// different user than whoever called RequestPublish. Before publishing, it
// asks policy-engine whether the candidate policy conflicts with any other
// currently-published policy for this tenant -- fail-closed: if
// policy-engine cannot be reached, the publish is blocked, not silently
// allowed through (approved architecture §22's fail-closed guarantee
// applies to conflict detection exactly as it does to evaluation).
func (s *Service) ApprovePublish(ctx context.Context, id uuid.UUID) (SovereigntyPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	p, exists, err := getPolicyByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if !exists {
		return SovereigntyPolicy{}, ErrPolicyNotFound
	}
	if p.Status != "pending_publish" {
		return SovereigntyPolicy{}, ErrNotPendingPublish
	}
	if p.RequestedBy == actor {
		return SovereigntyPolicy{}, ErrCannotSelfApprove
	}

	others, err := listOtherPublished(ctx, scopedTx.Tx, *scope.TenantID, p.PolicyKey)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	for _, other := range others {
		result, cerr := s.policyEngine.CheckConflicts(ctx, policyengine.ConflictCheckRequest{
			PolicyAID: p.ID.String(),
			PolicyA:   p.Document,
			PolicyBID: other.ID.String(),
			PolicyB:   other.Document,
		})
		if cerr != nil || result.HasConflicts {
			return SovereigntyPolicy{}, fmt.Errorf("%w (against %q): %v", ErrPublishBlockedByConflict, other.PolicyKey, result.Conflicts)
		}
	}

	if err := supersedeCurrentPublished(ctx, scopedTx.Tx, *scope.TenantID, p.PolicyKey); err != nil {
		return SovereigntyPolicy{}, err
	}
	ok, err := markApprovedAndPublished(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if !ok {
		return SovereigntyPolicy{}, ErrNotPendingPublish
	}
	published, exists, err := getPolicyByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if !exists {
		return SovereigntyPolicy{}, ErrPolicyNotFound
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "policies.published",
		TargetType:  "sovereignty_policy",
		TargetID:    &id,
		Evidence:    map[string]any{"policy_key": p.PolicyKey, "version": p.Version, "requested_by": p.RequestedBy},
	}); err != nil {
		return SovereigntyPolicy{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SovereigntyPolicy{}, err
	}
	return published, nil
}

// Rollback creates a new draft whose content matches an earlier version of
// the same policy_key -- it never mutates published history, and the new
// draft must go through the same request-publish/approve dual control as
// any other change before it takes effect.
func (s *Service) Rollback(ctx context.Context, policyKey string, toVersion int) (SovereigntyPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	versions, err := listVersionsByKey(ctx, scopedTx.Tx, *scope.TenantID, policyKey)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	var target *SovereigntyPolicy
	for i := range versions {
		if versions[i].Version == toVersion {
			target = &versions[i]
			break
		}
	}
	if target == nil {
		return SovereigntyPolicy{}, ErrPolicyNotFound
	}

	if _, exists, err := getDraftByKey(ctx, scopedTx.Tx, *scope.TenantID, policyKey); err != nil {
		return SovereigntyPolicy{}, err
	} else if exists {
		return SovereigntyPolicy{}, ErrDraftAlreadyExists
	}

	rolledBackFrom := toVersion
	p, err := createDraft(ctx, scopedTx.Tx, *scope.TenantID, policyKey, target.Name, target.Document, actor, &rolledBackFrom)
	if err != nil {
		return SovereigntyPolicy{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "policies.rollback_drafted",
		TargetType:  "sovereignty_policy",
		TargetID:    &p.ID,
		Evidence:    map[string]any{"policy_key": policyKey, "rolled_back_from_version": toVersion, "new_version": p.Version},
	}); err != nil {
		return SovereigntyPolicy{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SovereigntyPolicy{}, err
	}
	return p, nil
}

// Simulate runs the evaluator against a hypothetical candidate without
// persisting any evaluation record -- true "no side effects" simulation.
func (s *Service) Simulate(ctx context.Context, id uuid.UUID, candidate policyengine.EvaluationCandidate) (policyengine.EvaluationResult, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	p, exists, err := getPolicyByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return policyengine.EvaluationResult{}, err
	}
	if !exists {
		return policyengine.EvaluationResult{}, ErrPolicyNotFound
	}

	result, _ := s.policyEngine.Evaluate(ctx, policyengine.EvaluationRequest{
		PolicyID:      p.ID.String(),
		PolicyVersion: p.Version,
		Policy:        p.Document,
		Candidate:     candidate,
	})
	// Deliberately ignore the error here beyond what Evaluate already
	// encoded into result.Decision -- simulation has no evidence-integrity
	// obligation the way a real evaluation does, and the fail-closed
	// Decision is already safe to show the caller.
	return result, nil
}

// Evaluate runs a real evaluation against a policy's currently-published
// version and persists both a structured PolicyEvaluationRecord and a
// normal audit event -- this is what compliance evidence is built from.
func (s *Service) Evaluate(ctx context.Context, id uuid.UUID, candidate policyengine.EvaluationCandidate) (policyengine.EvaluationResult, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	p, exists, err := getPolicyByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return policyengine.EvaluationResult{}, err
	}
	if !exists {
		return policyengine.EvaluationResult{}, ErrPolicyNotFound
	}
	if p.Status != "published" {
		return policyengine.EvaluationResult{}, ErrPolicyNotPublished
	}

	result, evalErr := s.policyEngine.Evaluate(ctx, policyengine.EvaluationRequest{
		PolicyID:      p.ID.String(),
		PolicyVersion: p.Version,
		Policy:        p.Document,
		Candidate:     candidate,
	})

	candidateMap := map[string]any{
		"country":                          candidate.Country,
		"operator_id":                      candidate.OperatorID,
		"confidential_computing_available": candidate.ConfidentialComputingAvailable,
		"placement_role":                   candidate.PlacementRole,
		"encryption_key_ownership":         candidate.EncryptionKeyOwnership,
	}
	actorPtr := &actor
	evaluatedAt := time.Now()
	if _, err := createEvaluationRecord(ctx, scopedTx.Tx, *scope.TenantID, p.ID, p.Version, result.Decision, result.ReasonCodes, candidateMap, result.InputsHash, false, actorPtr, evaluatedAt); err != nil {
		return policyengine.EvaluationResult{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "policies.evaluated",
		TargetType:  "sovereignty_policy",
		TargetID:    &id,
		Evidence:    map[string]any{"decision": result.Decision, "reason_codes": result.ReasonCodes, "degraded": evalErr != nil},
	}); err != nil {
		return policyengine.EvaluationResult{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return policyengine.EvaluationResult{}, err
	}
	return result, nil
}

func (s *Service) ListEvaluationRecords(ctx context.Context) ([]EvaluationRecord, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listEvaluationRecords(ctx, scopedTx.Tx, *scope.TenantID)
}
