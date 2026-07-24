package placement

import (
	"context"
	"errors"
	"sort"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/policyengine"
)

// holdTTL is how long a reservation may sit in 'held' status awaiting
// dual-control approval before it lazily expires and its capacity is
// reclaimed (see repository.go's reclaimExpired). A fixed constant, not a
// per-tenant setting, is a deliberate simplification for this milestone.
const holdTTL = 15 * time.Minute

var (
	ErrVersionNotFound     = errors.New("workload version not found")
	ErrVersionNotPublished = errors.New("only a published workload version can be placed")
	ErrReservationNotFound = errors.New("capacity reservation not found")
	ErrNotHeld             = errors.New("capacity reservation is not in held status")
	ErrApprovalNotRequired = errors.New("this reservation's workload version does not require approval to commit")
	ErrCannotSelfApprove   = errors.New("the same user cannot both hold and approve a capacity reservation")
	ErrCannotCancel        = errors.New("capacity reservation cannot be cancelled from its current status")
)

type Service struct {
	store        *dbpkg.Store
	policyEngine *policyengine.Client
}

func NewService(store *dbpkg.Store, policyEngineClient *policyengine.Client) *Service {
	return &Service{store: store, policyEngine: policyEngineClient}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

func (s *Service) ListActiveOffers(ctx context.Context) ([]OfferSummary, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listActiveOffers(ctx, scopedTx.Tx)
}

// ListMyAgreements returns every bilateral agreement covering this tenant,
// across every operator that has established one -- Milestone 12's
// "enterprise eligibility" requirement made visible to the enterprise
// itself, not just the operator side.
func (s *Service) ListMyAgreements(ctx context.Context) ([]AgreementSummary, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listAgreementsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListPlacementRequests(ctx context.Context) ([]PlacementRequest, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listPlacementRequests(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListEvaluations(ctx context.Context, requestID uuid.UUID) ([]PlacementEvaluation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listEvaluationsForRequest(ctx, scopedTx.Tx, *scope.TenantID, requestID)
}

func (s *Service) ListReservations(ctx context.Context) ([]Reservation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listReservationsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

// eligibleCandidate pairs an already-persisted evaluation with the offer
// identity needed to actually reserve against it, kept separate from
// PlacementEvaluation because the evaluation row is immutable evidence
// while rank still needs to be assigned after sorting.
type eligibleCandidate struct {
	evaluation PlacementEvaluation
	offerID    uuid.UUID
	operatorID uuid.UUID
	unitPrice  float64
}

// EvaluatePlacement runs the approved architecture's 14-step placement
// order, steps 1-13, against every currently active capacity offer for one
// placement request. See model.go's package doc for the full step
// breakdown. simulate=true stops after ranking/explanation -- no capacity
// is ever reserved.
func (s *Service) EvaluatePlacement(ctx context.Context, versionID uuid.UUID, quantity int, simulate bool) (EvaluatePlacementResult, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	if err := reclaimExpired(ctx, scopedTx.Tx); err != nil {
		return EvaluatePlacementResult{}, err
	}

	facts, exists, err := getWorkloadVersionFacts(ctx, scopedTx.Tx, tenantID, versionID)
	if err != nil {
		return EvaluatePlacementResult{}, err
	}
	if !exists {
		return EvaluatePlacementResult{}, ErrVersionNotFound
	}
	if facts.Status != "published" {
		return EvaluatePlacementResult{}, ErrVersionNotPublished
	}

	req, err := createPlacementRequest(ctx, scopedTx.Tx, tenantID, versionID, quantity, simulate, actor)
	if err != nil {
		return EvaluatePlacementResult{}, err
	}

	offers, err := listActiveOffers(ctx, scopedTx.Tx)
	if err != nil {
		return EvaluatePlacementResult{}, err
	}
	sovereigntyPolicies, err := listPublishedSovereigntyPolicies(ctx, scopedTx.Tx, tenantID)
	if err != nil {
		return EvaluatePlacementResult{}, err
	}
	grantPriceOverrides, err := listActiveGrantPriceOverrides(ctx, scopedTx.Tx, tenantID)
	if err != nil {
		return EvaluatePlacementResult{}, err
	}

	requireConfidentialComputing, _ := facts.SecurityRequirements["confidential_computing_required"].(bool)
	requiredAcceleratorType, _ := facts.ResourceRequirements["gpu_type"].(string)
	var encryptionKeyOwnership *string
	if v, ok := facts.SecurityRequirements["encryption_key_ownership"].(string); ok && v != "" {
		encryptionKeyOwnership = &v
	}

	evaluatedAt := time.Now()
	evaluations := make([]PlacementEvaluation, 0, len(offers))
	eligible := make([]eligibleCandidate, 0, len(offers))

	for _, offer := range offers {
		explanation := map[string]any{}
		var reasonCodes []string
		isEligible := true

		// Step 2: sovereignty -- every published policy must allow.
		country, err := regionCountryCode(ctx, scopedTx.Tx, offer.RegionID)
		if err != nil {
			return EvaluatePlacementResult{}, err
		}
		candidate := policyengine.EvaluationCandidate{
			Country:                        country,
			OperatorID:                     offer.OperatorID.String(),
			ConfidentialComputingAvailable: offer.ConfidentialComputingAvailable,
			PlacementRole:                  "primary",
			EncryptionKeyOwnership:         encryptionKeyOwnership,
		}
		sovereigntyPassed := true
		sovereigntyTrace := make([]map[string]any, 0, len(sovereigntyPolicies))
		for _, pol := range sovereigntyPolicies {
			result, evalErr := s.policyEngine.Evaluate(ctx, policyengine.EvaluationRequest{
				PolicyID: pol.ID.String(), PolicyVersion: pol.Version, Policy: pol.Document, Candidate: candidate,
			})
			candidateMap := map[string]any{
				"country": candidate.Country, "operator_id": candidate.OperatorID,
				"confidential_computing_available": candidate.ConfidentialComputingAvailable,
				"placement_role":                   candidate.PlacementRole,
				"encryption_key_ownership":         candidate.EncryptionKeyOwnership,
			}
			if err := insertPolicyEvaluationRecord(ctx, scopedTx.Tx, tenantID, pol.ID, pol.Version, result.Decision,
				result.ReasonCodes, candidateMap, result.InputsHash, actor, evaluatedAt); err != nil {
				return EvaluatePlacementResult{}, err
			}
			sovereigntyTrace = append(sovereigntyTrace, map[string]any{
				"policy_id": pol.ID, "policy_version": pol.Version, "decision": result.Decision,
				"reason_codes": result.ReasonCodes, "policy_engine_degraded": evalErr != nil,
			})
			if result.Decision != policyengine.DecisionAllow {
				sovereigntyPassed = false
				reasonCodes = append(reasonCodes, result.ReasonCodes...)
			}
		}
		explanation["sovereignty"] = map[string]any{"passed": sovereigntyPassed, "policies_evaluated": sovereigntyTrace}
		if !sovereigntyPassed {
			isEligible = false
		}

		// Step 3: security requirements (confidential computing).
		securityPassed := !requireConfidentialComputing || offer.ConfidentialComputingAvailable
		explanation["security"] = map[string]any{
			"confidential_computing_required": requireConfidentialComputing,
			"offer_confidential_computing":    offer.ConfidentialComputingAvailable,
			"passed":                          securityPassed,
		}
		if !securityPassed {
			reasonCodes = append(reasonCodes, "CONFIDENTIAL_COMPUTING_REQUIRED")
			isEligible = false
		}

		// Step 4: commercial eligibility -- a private offer with no active
		// capacity_offer_grants row for this tenant never reaches this loop
		// at all (capacity_offers_enterprise_read's RLS policy already
		// filtered it out at the listActiveOffers query), so every offer
		// that does reach here is, by construction, one this tenant is
		// commercially eligible to see. unitPriceOverride is non-nil only
		// when an active grant carries a per-tenant price for this offer.
		unitPrice := offer.PricePerUnitHour
		unitPriceOverride, hasOverride := grantPriceOverrides[offer.ID]
		if hasOverride {
			unitPrice = unitPriceOverride
		}
		explanation["commercial_eligibility"] = map[string]any{
			"passed": true, "price_override_applied": hasOverride,
		}

		// Operator availability -- an operator that has self-declared this
		// offer degraded is excluded with an explained reason code, never
		// silently hidden. This is Milestone 12's "degraded-mode
		// handling"/"operator routing": a request that would have reserved
		// against a degraded offer is instead routed to the next eligible,
		// non-degraded candidate by the same ranking loop below.
		availabilityPassed := !offer.Degraded
		explanation["operator_availability"] = map[string]any{
			"degraded": offer.Degraded, "degraded_reason": offer.DegradedReason, "passed": availabilityPassed,
		}
		if !availabilityPassed {
			reasonCodes = append(reasonCodes, "OPERATOR_DEGRADED")
			isEligible = false
		}

		// Step 5: capacity.
		capacityPassed := offer.AvailableCapacity >= quantity
		explanation["capacity"] = map[string]any{
			"available_capacity": offer.AvailableCapacity, "requested_quantity": quantity, "passed": capacityPassed,
		}
		if !capacityPassed {
			reasonCodes = append(reasonCodes, "INSUFFICIENT_CAPACITY")
			isEligible = false
		}

		// Step 6: model/runtime compatibility -- accelerator type match.
		compatibilityPassed := requiredAcceleratorType == "" || requiredAcceleratorType == offer.AcceleratorType
		explanation["runtime_compatibility"] = map[string]any{
			"required_accelerator_type": requiredAcceleratorType, "offer_accelerator_type": offer.AcceleratorType,
			"passed": compatibilityPassed,
		}
		if !compatibilityPassed {
			reasonCodes = append(reasonCodes, "ACCELERATOR_TYPE_MISMATCH")
			isEligible = false
		}

		// Steps 7-8: network constraints and failover compatibility are not
		// yet enforced -- real network-slice verification is Milestone 9's
		// job, and failover-target compatibility depends on deployment
		// concepts this milestone does not build.
		explanation["network_constraints"] = map[string]any{"passed": true, "note": "not enforced until Milestone 9"}
		explanation["failover_compatibility"] = map[string]any{"passed": true, "note": "not enforced in this milestone"}

		// Step 9: cost and energy estimates -- priced at unitPrice, the
		// tenant's own grant override when one applies, never the offer's
		// base price in that case.
		estimatedCost := float64(quantity) * unitPrice
		estimatedEnergy := float64(quantity) * offer.EstimatedKWhPerUnitHour
		explanation["cost"] = map[string]any{"price_per_unit_hour": unitPrice, "estimated_cost": estimatedCost}
		explanation["energy"] = map[string]any{"estimated_kwh_per_unit_hour": offer.EstimatedKWhPerUnitHour, "estimated_energy_kwh": estimatedEnergy}

		decision := "rejected"
		if isEligible {
			decision = "eligible"
		}
		eval, err := insertEvaluation(ctx, scopedTx.Tx, tenantID, req.ID, offer.ID, offer.OperatorID, offer.RegionID,
			offer.AcceleratorType, decision, estimatedCost, estimatedEnergy, reasonCodes, explanation)
		if err != nil {
			return EvaluatePlacementResult{}, err
		}
		evaluations = append(evaluations, eval)
		if isEligible {
			eligible = append(eligible, eligibleCandidate{evaluation: eval, offerID: offer.ID, operatorID: offer.OperatorID, unitPrice: unitPrice})
		}
	}

	// Step 10: rank eligible targets -- a plain, deterministic sort (cost,
	// then energy, then offer id for a stable tie-break), never an
	// ML/LLM-based decision: every placement decision must be explainable,
	// and a non-deterministic ranking cannot be.
	sort.SliceStable(eligible, func(i, j int) bool {
		a, b := eligible[i].evaluation, eligible[j].evaluation
		if a.EstimatedCost != b.EstimatedCost {
			return a.EstimatedCost < b.EstimatedCost
		}
		if a.EstimatedEnergyKWh != b.EstimatedEnergyKWh {
			return a.EstimatedEnergyKWh < b.EstimatedEnergyKWh
		}
		return a.CapacityOfferID.String() < b.CapacityOfferID.String()
	})
	rankByEvaluationID := make(map[uuid.UUID]int, len(eligible))
	for i := range eligible {
		rank := i + 1
		if err := setEvaluationRank(ctx, scopedTx.Tx, eligible[i].evaluation.ID, rank); err != nil {
			return EvaluatePlacementResult{}, err
		}
		rankByEvaluationID[eligible[i].evaluation.ID] = rank
	}
	for i := range evaluations {
		if rank, ok := rankByEvaluationID[evaluations[i].ID]; ok {
			r := rank
			evaluations[i].Rank = &r
		}
	}

	result := EvaluatePlacementResult{Request: req, Evaluations: evaluations}

	if !simulate {
		// Step 12/13: reserve capacity atomically against the top-ranked
		// candidate, retrying down the ranked list if a lower-ranked
		// candidate lost the capacity race between evaluation and
		// reservation -- the contention handling this milestone requires.
		for _, candidate := range eligible {
			// reserveCapacity's own returned price is the offer's base
			// price, not this tenant's possibly-overridden one -- the
			// reservation is priced at candidate.unitPrice (resolved during
			// evaluation, in the same transaction, so it cannot have
			// drifted), never at whatever reserveCapacity itself returns.
			_, ok, err := reserveCapacity(ctx, scopedTx.Tx, candidate.offerID, quantity)
			if err != nil {
				return EvaluatePlacementResult{}, err
			}
			if !ok {
				continue
			}
			estimatedCost := float64(quantity) * candidate.unitPrice
			reservation, err := createReservation(ctx, scopedTx.Tx, tenantID, candidate.operatorID, req.ID, candidate.offerID,
				quantity, candidate.unitPrice, estimatedCost, facts.DeploymentApprovalRequired, actor, evaluatedAt.Add(holdTTL))
			if err != nil {
				return EvaluatePlacementResult{}, err
			}
			if !facts.DeploymentApprovalRequired {
				if _, err := markCommitted(ctx, scopedTx.Tx, reservation.ID, nil); err != nil {
					return EvaluatePlacementResult{}, err
				}
				now := time.Now()
				reservation.Status = "committed"
				reservation.CommittedAt = &now
			}
			result.Reservation = &reservation
			break
		}
		if result.Reservation != nil {
			if err := markPlacementRequestStatus(ctx, scopedTx.Tx, req.ID, "reserved"); err != nil {
				return EvaluatePlacementResult{}, err
			}
			result.Request.Status = "reserved"
		}
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "placement.evaluated", TargetType: "placement_request", TargetID: &req.ID,
		Evidence: map[string]any{
			"workload_version_id": versionID, "quantity": quantity, "simulate": simulate,
			"eligible_candidates": len(eligible), "reserved": result.Reservation != nil,
		},
	}); err != nil {
		return EvaluatePlacementResult{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return EvaluatePlacementResult{}, err
	}
	return result, nil
}

// ApproveCommitReservation is the dual-control gate for a reservation whose
// workload version has deployment_approval_required=true: a genuinely
// different user than whoever the placement request was made by must
// approve it before it becomes 'committed', enforced both here and by the
// capacity_reservations_no_self_approval DB CHECK constraint. A reservation
// whose version did not require approval is already 'committed' by the
// time EvaluatePlacement returns and never reaches this method.
func (s *Service) ApproveCommitReservation(ctx context.Context, id uuid.UUID) (Reservation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	if err := reclaimExpired(ctx, scopedTx.Tx); err != nil {
		return Reservation{}, err
	}

	res, exists, err := getReservationByID(ctx, scopedTx.Tx, tenantID, id)
	if err != nil {
		return Reservation{}, err
	}
	if !exists {
		return Reservation{}, ErrReservationNotFound
	}
	if res.Status != "held" {
		return Reservation{}, ErrNotHeld
	}
	if !res.ApprovalRequired {
		return Reservation{}, ErrApprovalNotRequired
	}
	if res.RequestedBy == actor {
		return Reservation{}, ErrCannotSelfApprove
	}

	ok, err := markCommitted(ctx, scopedTx.Tx, id, &actor)
	if err != nil {
		return Reservation{}, err
	}
	if !ok {
		return Reservation{}, ErrNotHeld
	}
	committed, exists, err := getReservationByID(ctx, scopedTx.Tx, tenantID, id)
	if err != nil {
		return Reservation{}, err
	}
	if !exists {
		return Reservation{}, ErrReservationNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "capacity_reservations.committed", TargetType: "capacity_reservation", TargetID: &id,
		Evidence: map[string]any{"requested_by": res.RequestedBy},
	}); err != nil {
		return Reservation{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Reservation{}, err
	}
	return committed, nil
}

// CancelReservation releases a held or committed reservation's capacity
// back to its offer. This milestone does not attempt to notify or roll
// back any downstream deployment -- there is none yet to roll back;
// cancelling a committed reservation once Milestone 7 exists to act on one
// is that milestone's problem to solve.
func (s *Service) CancelReservation(ctx context.Context, id uuid.UUID, reason string) (Reservation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	res, exists, err := getReservationByID(ctx, scopedTx.Tx, tenantID, id)
	if err != nil {
		return Reservation{}, err
	}
	if !exists {
		return Reservation{}, ErrReservationNotFound
	}

	ok, err := markReleased(ctx, scopedTx.Tx, id, reason)
	if err != nil {
		return Reservation{}, err
	}
	if !ok {
		return Reservation{}, ErrCannotCancel
	}
	if err := releaseCapacity(ctx, scopedTx.Tx, res.CapacityOfferID, res.Quantity); err != nil {
		return Reservation{}, err
	}
	if err := markPlacementRequestStatus(ctx, scopedTx.Tx, res.PlacementRequestID, "cancelled"); err != nil {
		return Reservation{}, err
	}

	cancelled, exists, err := getReservationByID(ctx, scopedTx.Tx, tenantID, id)
	if err != nil {
		return Reservation{}, err
	}
	if !exists {
		return Reservation{}, ErrReservationNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "capacity_reservations.cancelled", TargetType: "capacity_reservation", TargetID: &id,
		Evidence: map[string]any{"reason": reason, "previous_status": res.Status},
	}); err != nil {
		return Reservation{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Reservation{}, err
	}
	return cancelled, nil
}
