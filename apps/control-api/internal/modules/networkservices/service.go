package networkservices

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/pki"
)

// signedAtWindow bounds how far a machine-authenticated report's claimed
// signing time may drift from the server's clock -- the same
// replay-protection window internal/modules/deployments established for
// its own control-message result reporting (duplicated here rather than
// shared, per this codebase's established convention).
const signedAtWindow = 5 * time.Minute

var (
	ErrCapabilityNotFound     = errors.New("network capability not found or does not belong to this operator")
	ErrOfferNotFound          = errors.New("network service offer not found")
	ErrRequestNotFound        = errors.New("network service request not found")
	ErrReservationNotFound    = errors.New("network reservation not found")
	ErrReservationNotActive   = errors.New("network reservation is not committed")
	ErrNoTrustedCertificate   = errors.New("no currently valid certificate for this cluster agent")
	ErrInvalidSignature       = errors.New("signature verification failed")
	ErrReplay                 = errors.New("nonce already used or signing time outside the acceptance window")
	ErrControlMessageNotFound = errors.New("control message not found")
	ErrReservationMismatch    = errors.New("reported reservation does not match the original provision message")
	ErrActionMismatch         = errors.New("reported action does not match the original command")
)

type Service struct {
	store *dbpkg.Store
	ca    *pki.CA
}

func NewService(store *dbpkg.Store, ca *pki.CA) *Service {
	return &Service{store: store, ca: ca}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

// ---------------------------------------------------------------------
// Network service offers (operator-scoped)
// ---------------------------------------------------------------------

func (s *Service) CreateOffer(ctx context.Context, in CreateOfferInput) (NetworkServiceOffer, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	regionID, exists, err := networkCapabilityRegion(ctx, scopedTx.Tx, in.NetworkCapabilityID, *scope.OperatorID)
	if err != nil {
		return NetworkServiceOffer{}, err
	}
	if !exists {
		return NetworkServiceOffer{}, ErrCapabilityNotFound
	}

	o, err := createOffer(ctx, scopedTx.Tx, *scope.OperatorID, regionID, actor, in)
	if err != nil {
		return NetworkServiceOffer{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "network_service_offers.created", TargetType: "network_service_offer", TargetID: &o.ID,
		Evidence: map[string]any{"network_capability_id": in.NetworkCapabilityID, "service_class": in.ServiceClass, "total_bandwidth_gbps": in.TotalBandwidthGbps},
	}); err != nil {
		return NetworkServiceOffer{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return NetworkServiceOffer{}, err
	}
	return o, nil
}

func (s *Service) ListOffers(ctx context.Context) ([]NetworkServiceOffer, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listOffersForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) GetOffer(ctx context.Context, id uuid.UUID) (NetworkServiceOffer, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	o, exists, err := getOfferByID(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return NetworkServiceOffer{}, err
	}
	if !exists {
		return NetworkServiceOffer{}, ErrOfferNotFound
	}
	return o, nil
}

func (s *Service) UpdateOffer(ctx context.Context, id uuid.UUID, in UpdateOfferInput) (NetworkServiceOffer, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := updateOffer(ctx, scopedTx.Tx, *scope.OperatorID, id, in)
	if err != nil {
		return NetworkServiceOffer{}, err
	}
	if !ok {
		return NetworkServiceOffer{}, ErrOfferNotFound
	}
	o, exists, err := getOfferByID(ctx, scopedTx.Tx, *scope.OperatorID, id)
	if err != nil {
		return NetworkServiceOffer{}, err
	}
	if !exists {
		return NetworkServiceOffer{}, ErrOfferNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeOperator, ScopeID: scope.OperatorID,
		Action: "network_service_offers.updated", TargetType: "network_service_offer", TargetID: &id,
		Evidence: map[string]any{"status": o.Status, "available_bandwidth_gbps": o.AvailableBandwidthGbps},
	}); err != nil {
		return NetworkServiceOffer{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return NetworkServiceOffer{}, err
	}
	return o, nil
}

func (s *Service) ListOperatorReservations(ctx context.Context) ([]NetworkReservation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listReservationsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

func (s *Service) ListOperatorHealthEvents(ctx context.Context) ([]NetworkHealthEvent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listHealthEventsForOperator(ctx, scopedTx.Tx, *scope.OperatorID)
}

// ---------------------------------------------------------------------
// Enterprise-facing browsing, request/evaluate/reserve, cancel
// ---------------------------------------------------------------------

func (s *Service) ListActiveOffers(ctx context.Context) ([]OfferSummary, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listActiveOffers(ctx, scopedTx.Tx)
}

func (s *Service) ListRequests(ctx context.Context) ([]NetworkServiceRequest, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listRequestsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListEvaluations(ctx context.Context, requestID uuid.UUID) ([]NetworkServiceEvaluation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listEvaluationsForRequest(ctx, scopedTx.Tx, *scope.TenantID, requestID)
}

func (s *Service) ListTenantReservations(ctx context.Context) ([]NetworkReservation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listReservationsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) ListTenantHealthEvents(ctx context.Context) ([]NetworkHealthEvent, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listHealthEventsForTenant(ctx, scopedTx.Tx, *scope.TenantID)
}

// eligibleCandidate pairs an already-persisted evaluation with the offer
// identity needed to actually reserve against it -- mirrors
// internal/modules/placement's EvaluatePlacement type of the same name.
type eligibleCandidate struct {
	evaluation NetworkServiceEvaluation
	offerID    uuid.UUID
	operatorID uuid.UUID
}

// EvaluateAndReserve runs a deterministic eligibility/ranking pass against
// every currently active network service offer for one request, mirroring
// internal/modules/placement.EvaluatePlacement's explainability discipline:
// every candidate offer gets an explained, persisted evaluation record,
// eligible candidates are ranked by a plain deterministic sort (never an
// AI/ML ranking decision), and, unless simulate=true, the top-ranked
// candidate that still has capacity when actually reserved becomes a
// committed NetworkReservation with no dual-control step (see model.go's
// package doc for why). A committed reservation immediately attempts to
// provision by sending a signed control message to the resolved cluster
// agent; if no active cluster agent can be resolved for the winning
// offer's network capability, the reservation still commits (bandwidth is
// genuinely reserved) but provisioning_status stays 'failed' for visibility
// rather than blocking the commercial transaction on infrastructure that
// happens to be unreachable right now.
func (s *Service) EvaluateAndReserve(ctx context.Context, deploymentID *uuid.UUID, requiredBandwidthGbps float64, maxLatencyMs *float64, serviceClass *string, simulate bool) (EvaluateNetworkServiceResult, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	req, err := createRequest(ctx, scopedTx.Tx, tenantID, deploymentID, requiredBandwidthGbps, maxLatencyMs, serviceClass, simulate, actor)
	if err != nil {
		return EvaluateNetworkServiceResult{}, err
	}

	offers, err := listActiveOffers(ctx, scopedTx.Tx)
	if err != nil {
		return EvaluateNetworkServiceResult{}, err
	}

	evaluations := make([]NetworkServiceEvaluation, 0, len(offers))
	eligible := make([]eligibleCandidate, 0, len(offers))

	for _, offer := range offers {
		explanation := map[string]any{}
		var reasonCodes []string
		isEligible := true

		bandwidthPassed := offer.AvailableBandwidthGbps >= requiredBandwidthGbps
		explanation["bandwidth"] = map[string]any{
			"available_bandwidth_gbps": offer.AvailableBandwidthGbps, "required_bandwidth_gbps": requiredBandwidthGbps, "passed": bandwidthPassed,
		}
		if !bandwidthPassed {
			reasonCodes = append(reasonCodes, "INSUFFICIENT_BANDWIDTH")
			isEligible = false
		}

		latencyPassed := maxLatencyMs == nil || offer.MaxLatencyMs == nil || *offer.MaxLatencyMs <= *maxLatencyMs
		explanation["latency"] = map[string]any{
			"required_max_latency_ms": maxLatencyMs, "offer_max_latency_ms": offer.MaxLatencyMs, "passed": latencyPassed,
		}
		if !latencyPassed {
			reasonCodes = append(reasonCodes, "LATENCY_OBJECTIVE_NOT_MET")
			isEligible = false
		}

		classPassed := serviceClass == nil || *serviceClass == offer.ServiceClass
		explanation["service_class"] = map[string]any{
			"required_service_class": serviceClass, "offer_service_class": offer.ServiceClass, "passed": classPassed,
		}
		if !classPassed {
			reasonCodes = append(reasonCodes, "SERVICE_CLASS_MISMATCH")
			isEligible = false
		}

		estimatedCost := requiredBandwidthGbps * offer.PricePerUnitHour
		explanation["cost"] = map[string]any{"price_per_unit_hour": offer.PricePerUnitHour, "estimated_cost": estimatedCost}

		decision := "rejected"
		if isEligible {
			decision = "eligible"
		}
		eval, err := insertEvaluation(ctx, scopedTx.Tx, tenantID, req.ID, offer.ID, offer.OperatorID, offer.RegionID,
			offer.ServiceClass, decision, estimatedCost, reasonCodes, explanation)
		if err != nil {
			return EvaluateNetworkServiceResult{}, err
		}
		evaluations = append(evaluations, eval)
		if isEligible {
			eligible = append(eligible, eligibleCandidate{evaluation: eval, offerID: offer.ID, operatorID: offer.OperatorID})
		}
	}

	// Rank eligible targets -- a plain, deterministic sort (cost, then offer
	// id for a stable tie-break), never an ML/LLM-based decision.
	sort.SliceStable(eligible, func(i, j int) bool {
		a, b := eligible[i].evaluation, eligible[j].evaluation
		if a.EstimatedCost != b.EstimatedCost {
			return a.EstimatedCost < b.EstimatedCost
		}
		return a.NetworkServiceOfferID.String() < b.NetworkServiceOfferID.String()
	})
	rankByEvaluationID := make(map[uuid.UUID]int, len(eligible))
	for i := range eligible {
		rank := i + 1
		if err := setEvaluationRank(ctx, scopedTx.Tx, eligible[i].evaluation.ID, rank); err != nil {
			return EvaluateNetworkServiceResult{}, err
		}
		rankByEvaluationID[eligible[i].evaluation.ID] = rank
	}
	for i := range evaluations {
		if rank, ok := rankByEvaluationID[evaluations[i].ID]; ok {
			r := rank
			evaluations[i].Rank = &r
		}
	}

	result := EvaluateNetworkServiceResult{Request: req, Evaluations: evaluations}

	if !simulate {
		for _, candidate := range eligible {
			pricePerUnitHour, ok, err := reserveBandwidth(ctx, scopedTx.Tx, candidate.offerID, requiredBandwidthGbps)
			if err != nil {
				return EvaluateNetworkServiceResult{}, err
			}
			if !ok {
				continue
			}
			estimatedCost := requiredBandwidthGbps * pricePerUnitHour

			var clusterAgentID *uuid.UUID
			var agentID uuid.UUID
			var agentFound bool
			if err := withPlatformBypass(ctx, scopedTx.Tx, func() error {
				var berr error
				agentID, agentFound, berr = activeClusterAgentForOffer(ctx, scopedTx.Tx, candidate.offerID)
				return berr
			}); err != nil {
				return EvaluateNetworkServiceResult{}, err
			}
			if agentFound {
				clusterAgentID = &agentID
			}

			reservation, err := createReservation(ctx, scopedTx.Tx, tenantID, candidate.operatorID, req.ID, candidate.offerID,
				deploymentID, clusterAgentID, requiredBandwidthGbps, pricePerUnitHour, estimatedCost, actor)
			if err != nil {
				return EvaluateNetworkServiceResult{}, err
			}

			if agentFound {
				if err := s.sendProvisionCommand(ctx, scopedTx.Tx, candidate.operatorID, agentID, reservation, candidate.evaluation.ServiceClass); err != nil {
					return EvaluateNetworkServiceResult{}, err
				}
				if err := setProvisioningStatus(ctx, scopedTx.Tx, reservation.ID, "pending"); err != nil {
					return EvaluateNetworkServiceResult{}, err
				}
			} else {
				if err := setProvisioningStatus(ctx, scopedTx.Tx, reservation.ID, "failed"); err != nil {
					return EvaluateNetworkServiceResult{}, err
				}
				reservation.ProvisioningStatus = "failed"
			}

			result.Reservation = &reservation
			break
		}
		if result.Reservation != nil {
			if err := markRequestStatus(ctx, scopedTx.Tx, req.ID, "reserved"); err != nil {
				return EvaluateNetworkServiceResult{}, err
			}
			result.Request.Status = "reserved"
		}
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "network_services.evaluated", TargetType: "network_service_request", TargetID: &req.ID,
		Evidence: map[string]any{
			"required_bandwidth_gbps": requiredBandwidthGbps, "simulate": simulate,
			"eligible_candidates": len(eligible), "reserved": result.Reservation != nil,
		},
	}); err != nil {
		return EvaluateNetworkServiceResult{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return EvaluateNetworkServiceResult{}, err
	}
	return result, nil
}

// CancelReservation releases a committed reservation's bandwidth back to
// its offer and, if it was provisioned, tells the cluster agent to release
// the service too. Mirrors internal/modules/placement.CancelReservation's
// shape.
func (s *Service) CancelReservation(ctx context.Context, id uuid.UUID, reason string) (NetworkReservation, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)
	tenantID := *scope.TenantID

	res, exists, err := getReservationByIDForTenant(ctx, scopedTx.Tx, tenantID, id)
	if err != nil {
		return NetworkReservation{}, err
	}
	if !exists {
		return NetworkReservation{}, ErrReservationNotFound
	}
	if res.Status != "committed" {
		return NetworkReservation{}, ErrReservationNotActive
	}

	ok, err := markReservationReleased(ctx, scopedTx.Tx, id, reason)
	if err != nil {
		return NetworkReservation{}, err
	}
	if !ok {
		return NetworkReservation{}, ErrReservationNotActive
	}
	if err := releaseBandwidth(ctx, scopedTx.Tx, res.NetworkServiceOfferID, res.BandwidthGbps); err != nil {
		return NetworkReservation{}, err
	}

	if res.ClusterAgentID != nil && res.ProvisioningStatus == "provisioned" {
		if err := s.sendReleaseCommand(ctx, scopedTx.Tx, res.OperatorID, *res.ClusterAgentID, res); err != nil {
			return NetworkReservation{}, err
		}
	}

	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "network_reservations.cancelled", TargetType: "network_reservation", TargetID: &id,
		Evidence: map[string]any{"reason": reason},
	}); err != nil {
		return NetworkReservation{}, err
	}
	updated, exists, err := getReservationByIDForTenant(ctx, scopedTx.Tx, tenantID, id)
	if err != nil {
		return NetworkReservation{}, err
	}
	if !exists {
		return NetworkReservation{}, ErrReservationNotFound
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return NetworkReservation{}, err
	}
	return updated, nil
}

// ---------------------------------------------------------------------
// Control message signing helpers
// ---------------------------------------------------------------------

func (s *Service) sendProvisionCommand(ctx context.Context, tx conn, operatorID, agentID uuid.UUID, reservation NetworkReservation, serviceClass string) error {
	payload := networkProvisionPayload{
		Action: "provision", ReservationID: reservation.ID.String(),
		BandwidthGbps: reservation.BandwidthGbps, ServiceClass: serviceClass,
	}
	return s.sendNetworkCommand(ctx, tx, operatorID, agentID, payload)
}

func (s *Service) sendReleaseCommand(ctx context.Context, tx conn, operatorID, agentID uuid.UUID, reservation NetworkReservation) error {
	payload := networkProvisionPayload{Action: "release", ReservationID: reservation.ID.String()}
	return s.sendNetworkCommand(ctx, tx, operatorID, agentID, payload)
}

// sendNetworkCommand signs and persists a to_agent network_service_provision
// control message -- the same signed, replay-protected mechanism
// internal/modules/deployments' sendCommand established, addressed to the
// cluster agent resolved for this reservation's offer's network capability.
func (s *Service) sendNetworkCommand(ctx context.Context, tx conn, operatorID, agentID uuid.UUID, payload networkProvisionPayload) error {
	payloadJSON, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("encode network service command: %w", err)
	}
	signature, err := s.ca.SignMessage(payloadJSON)
	if err != nil {
		return fmt.Errorf("sign network service command: %w", err)
	}
	nonce, err := generateNonce()
	if err != nil {
		return err
	}
	return withPlatformBypass(ctx, tx, func() error {
		_, err := createControlMessage(ctx, tx, operatorID, agentID, "to_agent", "network_service_provision",
			nil, nonce, payloadJSON, signature, time.Now(), "pending")
		return err
	})
}

func generateNonce() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("generate nonce: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

// ---------------------------------------------------------------------
// Agent-facing (machine-authenticated, no session)
// ---------------------------------------------------------------------

// AgentReportProvisionResult records a cluster agent's signed report of
// what happened when it executed a network_service_provision command --
// mirrors internal/modules/deployments.AgentReportCommandResult exactly:
// signature verified against the agent's current certificate, nonce
// uniqueness checked before any write, claimed signing time bounded by
// signedAtWindow. The outcome is recorded both as the reservation's new
// provisioning_status and as an append-only network_health_event so an
// operator has a permanent record of every provisioning attempt.
func (s *Service) AgentReportProvisionResult(ctx context.Context, agentID, messageID uuid.UUID, rawBody []byte, signatureB64 string) (NetworkHealthEvent, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	operatorID, certPEM, ok, err := clusterAgentIdentity(ctx, tx, agentID)
	if err != nil {
		return NetworkHealthEvent{}, err
	}
	if !ok {
		return NetworkHealthEvent{}, ErrNoTrustedCertificate
	}
	valid, err := pki.VerifySignature(certPEM, rawBody, signatureB64)
	if err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("%w: %v", ErrInvalidSignature, err)
	}
	if !valid {
		return NetworkHealthEvent{}, ErrInvalidSignature
	}

	var body networkProvisionResult
	if err := json.Unmarshal(rawBody, &body); err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("decode network provision result: %w", err)
	}
	signedAt, err := time.Parse(time.RFC3339, body.SignedAt)
	if err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("%w: invalid signed_at", ErrReplay)
	}
	if time.Since(signedAt).Abs() > signedAtWindow {
		return NetworkHealthEvent{}, ErrReplay
	}
	nonceUsed, err := controlMessageNonceExists(ctx, tx, agentID, body.Nonce)
	if err != nil {
		return NetworkHealthEvent{}, err
	}
	if nonceUsed {
		return NetworkHealthEvent{}, ErrReplay
	}

	original, exists, err := getPendingProvisionMessage(ctx, tx, agentID, messageID)
	if err != nil {
		return NetworkHealthEvent{}, err
	}
	if !exists {
		return NetworkHealthEvent{}, ErrControlMessageNotFound
	}
	reservationID, err := uuid.Parse(original.ReservationID)
	if err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("decode original command reservation_id: %w", err)
	}
	if reservationID.String() != body.ReservationID {
		return NetworkHealthEvent{}, ErrReservationMismatch
	}
	if original.Action != body.Action {
		return NetworkHealthEvent{}, ErrActionMismatch
	}

	if _, err := createControlMessage(ctx, tx, operatorID, agentID, "from_agent", "network_service_provision_result",
		&messageID, body.Nonce, rawBody, signatureB64, signedAt, "responded"); err != nil {
		return NetworkHealthEvent{}, err
	}
	if ok, err := markControlMessageResponded(ctx, tx, messageID); err != nil {
		return NetworkHealthEvent{}, err
	} else if !ok {
		return NetworkHealthEvent{}, ErrControlMessageNotFound
	}

	reservation, exists, err := getReservationByIDAnyScope(ctx, tx, reservationID)
	if err != nil {
		return NetworkHealthEvent{}, err
	}
	if !exists {
		return NetworkHealthEvent{}, ErrReservationNotFound
	}

	// provisioning_status only ever tracks the 'provision' action's outcome
	// (its CHECK constraint has no 'released' value -- reservation.status
	// already captures that, set synchronously by CancelReservation before
	// this release command is even sent); a 'release' result is recorded as
	// a health event only.
	severity := "critical"
	eventType := body.Action + "_failed"
	if body.Success {
		severity = "info"
		eventType = body.Action + "_succeeded"
	}
	if body.Action == "provision" {
		newStatus := "failed"
		if body.Success {
			newStatus = "provisioned"
		}
		if err := setProvisioningStatus(ctx, tx, reservationID, newStatus); err != nil {
			return NetworkHealthEvent{}, err
		}
	}

	event, err := insertHealthEvent(ctx, tx, operatorID, &reservation.EnterpriseTenantID, &reservationID, eventType, severity,
		map[string]any{"action": body.Action, "success": body.Success, "detail": body.Detail}, signedAt)
	if err != nil {
		return NetworkHealthEvent{}, err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ScopeType: audit.ScopeOperator, ScopeID: &operatorID,
		Action: "network_reservations.provision_result", TargetType: "network_reservation", TargetID: &reservationID,
		Evidence: map[string]any{"success": body.Success, "cluster_agent_id": agentID},
	}); err != nil {
		return NetworkHealthEvent{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("commit network provision result: %w", err)
	}
	return event, nil
}
