package placement

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"

	"gridkeep/control-api/internal/platform/policyengine"
)

// conn is satisfied by both *pgxpool.Pool and pgx.Tx, matching the pattern
// every other module's repository layer uses.
type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// ---------------------------------------------------------------------
// Capacity offers (read-only from this package's perspective -- the
// enterprise_read RLS policy on capacity_offers already restricts what
// comes back to active offers regardless of which operator owns them; the
// capacityoffers package owns writes).
// ---------------------------------------------------------------------

func listActiveOffers(ctx context.Context, c conn) ([]OfferSummary, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, region_id, accelerator_type, available_capacity, price_per_unit_hour,
			currency, confidential_computing_available, estimated_kwh_per_unit_hour, degraded, degraded_reason
		FROM capacity_offers WHERE status = 'active' ORDER BY id
	`)
	if err != nil {
		return nil, fmt.Errorf("list active capacity offers: %w", err)
	}
	defer rows.Close()

	var out []OfferSummary
	for rows.Next() {
		var o OfferSummary
		if err := rows.Scan(&o.ID, &o.OperatorID, &o.RegionID, &o.AcceleratorType, &o.AvailableCapacity,
			&o.PricePerUnitHour, &o.Currency, &o.ConfidentialComputingAvailable, &o.EstimatedKWhPerUnitHour,
			&o.Degraded, &o.DegradedReason); err != nil {
			return nil, fmt.Errorf("scan capacity offer: %w", err)
		}
		out = append(out, o)
	}
	return out, rows.Err()
}

// grantPriceOverride is the one field EvaluatePlacement needs from a
// capacity_offer_grants row -- the per-tenant price this specific tenant
// pays instead of the offer's own base price, when one has been granted.
type grantPriceOverride struct {
	capacityOfferID uuid.UUID
	unitPrice       float64
}

// listActiveGrantPriceOverrides fetches every active grant with a
// non-null price override for this tenant, keyed by offer id, in one round
// trip -- avoiding an N+1 lookup inside EvaluatePlacement's per-offer loop.
// Grant existence for private-offer *visibility* is already handled
// transparently by capacity_offers' own RLS policy (a private offer with no
// grant for this tenant never appears in listActiveOffers' result at all);
// this query exists purely for pricing, which RLS cannot express.
func listActiveGrantPriceOverrides(ctx context.Context, c conn, tenantID uuid.UUID) (map[uuid.UUID]float64, error) {
	rows, err := c.Query(ctx, `
		SELECT capacity_offer_id, price_per_unit_hour_override FROM capacity_offer_grants
		WHERE enterprise_tenant_id = $1 AND status = 'active' AND price_per_unit_hour_override IS NOT NULL
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list active capacity offer grant price overrides: %w", err)
	}
	defer rows.Close()
	out := map[uuid.UUID]float64{}
	for rows.Next() {
		var o grantPriceOverride
		if err := rows.Scan(&o.capacityOfferID, &o.unitPrice); err != nil {
			return nil, fmt.Errorf("scan capacity offer grant price override: %w", err)
		}
		out[o.capacityOfferID] = o.unitPrice
	}
	return out, rows.Err()
}

// listAgreementsForTenant reads bilateral_agreements directly -- a table
// internal/modules/capacityoffers owns writes to -- the same "each module
// owns its own SQL against shared tables" convention this codebase has
// applied since Milestone 9. Visibility is already restricted to this
// tenant's own agreements by bilateral_agreements_tenant_read's RLS policy.
func listAgreementsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]AgreementSummary, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, status, currency, platform_fee_rate, created_at
		FROM bilateral_agreements WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list bilateral agreements for tenant: %w", err)
	}
	defer rows.Close()
	out := []AgreementSummary{}
	for rows.Next() {
		var a AgreementSummary
		if err := rows.Scan(&a.ID, &a.OperatorID, &a.Status, &a.Currency, &a.PlatformFeeRate, &a.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan bilateral agreement: %w", err)
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// regionCountryCode resolves a region to its jurisdiction's ISO country
// code -- the "country" field a sovereignty-policy candidate is evaluated
// against.
func regionCountryCode(ctx context.Context, c conn, regionID uuid.UUID) (string, error) {
	var code string
	err := c.QueryRow(ctx, `
		SELECT j.country_code FROM regions r JOIN jurisdictions j ON j.id = r.jurisdiction_id WHERE r.id = $1
	`, regionID).Scan(&code)
	if err != nil {
		return "", fmt.Errorf("look up region country code: %w", err)
	}
	return code, nil
}

// ---------------------------------------------------------------------
// Workload version (read-only; owned by the workloads module).
// ---------------------------------------------------------------------

type workloadVersionFacts struct {
	Status                     string
	ResourceRequirements       map[string]any
	SecurityRequirements       map[string]any
	DeploymentApprovalRequired bool
}

func getWorkloadVersionFacts(ctx context.Context, c conn, tenantID, versionID uuid.UUID) (workloadVersionFacts, bool, error) {
	var f workloadVersionFacts
	var resourceRaw, securityRaw []byte
	err := c.QueryRow(ctx, `
		SELECT status, resource_requirements, security_requirements, deployment_approval_required
		FROM workload_versions WHERE id = $1 AND enterprise_tenant_id = $2
	`, versionID, tenantID).Scan(&f.Status, &resourceRaw, &securityRaw, &f.DeploymentApprovalRequired)
	if err != nil {
		if err == pgx.ErrNoRows {
			return workloadVersionFacts{}, false, nil
		}
		return workloadVersionFacts{}, false, fmt.Errorf("look up workload version: %w", err)
	}
	if err := json.Unmarshal(resourceRaw, &f.ResourceRequirements); err != nil {
		return workloadVersionFacts{}, false, fmt.Errorf("decode resource requirements: %w", err)
	}
	if err := json.Unmarshal(securityRaw, &f.SecurityRequirements); err != nil {
		return workloadVersionFacts{}, false, fmt.Errorf("decode security requirements: %w", err)
	}
	return f, true, nil
}

// ---------------------------------------------------------------------
// Sovereignty policies (read + evidence write; sovereignty_policies is
// owned by the policies module, policy_evaluation_records is shared
// structured evidence every real evaluation writes to regardless of which
// module ran it).
// ---------------------------------------------------------------------

type publishedPolicy struct {
	ID       uuid.UUID
	Version  int
	Document policyengine.PolicyDocument
}

func listPublishedSovereigntyPolicies(ctx context.Context, c conn, tenantID uuid.UUID) ([]publishedPolicy, error) {
	rows, err := c.Query(ctx, `
		SELECT id, version, document FROM sovereignty_policies
		WHERE enterprise_tenant_id = $1 AND status = 'published'
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list published sovereignty policies: %w", err)
	}
	defer rows.Close()

	var out []publishedPolicy
	for rows.Next() {
		var p publishedPolicy
		var raw []byte
		if err := rows.Scan(&p.ID, &p.Version, &raw); err != nil {
			return nil, fmt.Errorf("scan sovereignty policy: %w", err)
		}
		if err := json.Unmarshal(raw, &p.Document); err != nil {
			return nil, fmt.Errorf("decode sovereignty policy document: %w", err)
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// insertPolicyEvaluationRecord writes into the same append-only
// policy_evaluation_records table the policies module's own Evaluate
// method writes to (migration 0017) -- this is structured compliance
// evidence for "a sovereignty policy was evaluated", not something owned
// exclusively by the policies module's HTTP-facing simulate/evaluate
// endpoints.
func insertPolicyEvaluationRecord(ctx context.Context, c conn, tenantID, policyID uuid.UUID, policyVersion int, decision string, reasonCodes []string, candidate map[string]any, inputsHash string, evaluatedBy uuid.UUID, evaluatedAt time.Time) error {
	reasonCodesJSON, err := json.Marshal(reasonCodes)
	if err != nil {
		return fmt.Errorf("encode reason codes: %w", err)
	}
	candidateJSON, err := json.Marshal(candidate)
	if err != nil {
		return fmt.Errorf("encode candidate: %w", err)
	}
	_, err = c.Exec(ctx, `
		INSERT INTO policy_evaluation_records (
			enterprise_tenant_id, sovereignty_policy_id, policy_version, decision, reason_codes,
			candidate, inputs_hash, is_simulation, evaluated_by, evaluated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, $8, $9)
	`, tenantID, policyID, policyVersion, decision, reasonCodesJSON, candidateJSON, inputsHash, evaluatedBy, evaluatedAt)
	if err != nil {
		return fmt.Errorf("insert policy evaluation record: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Placement requests / evaluations
// ---------------------------------------------------------------------

func createPlacementRequest(ctx context.Context, c conn, tenantID, versionID uuid.UUID, quantity int, simulate bool, requestedBy uuid.UUID) (PlacementRequest, error) {
	var req PlacementRequest
	err := c.QueryRow(ctx, `
		INSERT INTO placement_requests (enterprise_tenant_id, workload_version_id, quantity, simulate, requested_by)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, enterprise_tenant_id, workload_version_id, quantity, simulate, status, requested_by, created_at, updated_at
	`, tenantID, versionID, quantity, simulate, requestedBy).Scan(
		&req.ID, &req.EnterpriseTenantID, &req.WorkloadVersionID, &req.Quantity, &req.Simulate,
		&req.Status, &req.RequestedBy, &req.CreatedAt, &req.UpdatedAt)
	if err != nil {
		return PlacementRequest{}, fmt.Errorf("insert placement request: %w", err)
	}
	return req, nil
}

func markPlacementRequestStatus(ctx context.Context, c conn, id uuid.UUID, status string) error {
	_, err := c.Exec(ctx, `UPDATE placement_requests SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("update placement request status: %w", err)
	}
	return nil
}

func listPlacementRequests(ctx context.Context, c conn, tenantID uuid.UUID) ([]PlacementRequest, error) {
	rows, err := c.Query(ctx, `
		SELECT id, enterprise_tenant_id, workload_version_id, quantity, simulate, status, requested_by, created_at, updated_at
		FROM placement_requests WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list placement requests: %w", err)
	}
	defer rows.Close()

	var out []PlacementRequest
	for rows.Next() {
		var req PlacementRequest
		if err := rows.Scan(&req.ID, &req.EnterpriseTenantID, &req.WorkloadVersionID, &req.Quantity, &req.Simulate,
			&req.Status, &req.RequestedBy, &req.CreatedAt, &req.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan placement request: %w", err)
		}
		out = append(out, req)
	}
	return out, rows.Err()
}

func insertEvaluation(ctx context.Context, c conn, tenantID, requestID, offerID, operatorID, regionID uuid.UUID, acceleratorType, decision string, cost, energy float64, reasonCodes []string, explanation map[string]any) (PlacementEvaluation, error) {
	reasonCodesJSON, err := json.Marshal(reasonCodes)
	if err != nil {
		return PlacementEvaluation{}, fmt.Errorf("encode reason codes: %w", err)
	}
	explanationJSON, err := json.Marshal(explanation)
	if err != nil {
		return PlacementEvaluation{}, fmt.Errorf("encode explanation: %w", err)
	}
	var e PlacementEvaluation
	var reasonRaw, explanationRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO placement_evaluations (
			enterprise_tenant_id, placement_request_id, capacity_offer_id, operator_id, region_id,
			accelerator_type, decision, estimated_cost, estimated_energy_kwh, reason_codes, explanation
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		RETURNING id, placement_request_id, capacity_offer_id, operator_id, region_id, accelerator_type,
			decision, rank, estimated_cost, estimated_energy_kwh, reason_codes, explanation, created_at
	`, tenantID, requestID, offerID, operatorID, regionID, acceleratorType, decision, cost, energy, reasonCodesJSON, explanationJSON).Scan(
		&e.ID, &e.PlacementRequestID, &e.CapacityOfferID, &e.OperatorID, &e.RegionID, &e.AcceleratorType,
		&e.Decision, &e.Rank, &e.EstimatedCost, &e.EstimatedEnergyKWh, &reasonRaw, &explanationRaw, &e.CreatedAt)
	if err != nil {
		return PlacementEvaluation{}, fmt.Errorf("insert placement evaluation: %w", err)
	}
	if err := json.Unmarshal(reasonRaw, &e.ReasonCodes); err != nil {
		return PlacementEvaluation{}, fmt.Errorf("decode reason codes: %w", err)
	}
	if err := json.Unmarshal(explanationRaw, &e.Explanation); err != nil {
		return PlacementEvaluation{}, fmt.Errorf("decode explanation: %w", err)
	}
	return e, nil
}

func setEvaluationRank(ctx context.Context, c conn, id uuid.UUID, rank int) error {
	_, err := c.Exec(ctx, `UPDATE placement_evaluations SET rank = $2 WHERE id = $1`, id, rank)
	if err != nil {
		return fmt.Errorf("set evaluation rank: %w", err)
	}
	return nil
}

func listEvaluationsForRequest(ctx context.Context, c conn, tenantID, requestID uuid.UUID) ([]PlacementEvaluation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, placement_request_id, capacity_offer_id, operator_id, region_id, accelerator_type,
			decision, rank, estimated_cost, estimated_energy_kwh, reason_codes, explanation, created_at
		FROM placement_evaluations WHERE enterprise_tenant_id = $1 AND placement_request_id = $2
		ORDER BY (rank IS NULL), rank, estimated_cost
	`, tenantID, requestID)
	if err != nil {
		return nil, fmt.Errorf("list placement evaluations: %w", err)
	}
	defer rows.Close()

	var out []PlacementEvaluation
	for rows.Next() {
		var e PlacementEvaluation
		var reasonRaw, explanationRaw []byte
		if err := rows.Scan(&e.ID, &e.PlacementRequestID, &e.CapacityOfferID, &e.OperatorID, &e.RegionID, &e.AcceleratorType,
			&e.Decision, &e.Rank, &e.EstimatedCost, &e.EstimatedEnergyKWh, &reasonRaw, &explanationRaw, &e.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan placement evaluation: %w", err)
		}
		if err := json.Unmarshal(reasonRaw, &e.ReasonCodes); err != nil {
			return nil, fmt.Errorf("decode reason codes: %w", err)
		}
		if err := json.Unmarshal(explanationRaw, &e.Explanation); err != nil {
			return nil, fmt.Errorf("decode explanation: %w", err)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Atomic capacity locking + lazy expiry reclamation
// ---------------------------------------------------------------------

// withPlatformBypass runs fn with app.platform_bypass set for the
// remainder of the current statement only, then immediately unsets it --
// used exclusively by the three functions below, which are the one place
// in this codebase where a legitimate tenant-scoped action (reserving or
// releasing capacity against a placement request) must write into a
// capacity_offers row it does not own under that table's normal RLS
// policies (only the owning operator, or true platform bypass, may UPDATE
// it; the tenant-facing capacity_offers_enterprise_read policy is
// SELECT-only by design). The statements this wraps are fixed, parameterized,
// and never take raw user input beyond an id/quantity already validated by
// the caller, so the elevation is narrow and auditable -- not a general
// escape hatch.
func withPlatformBypass(ctx context.Context, c conn, fn func() error) error {
	if _, err := c.Exec(ctx, `SET LOCAL app.platform_bypass = 'true'`); err != nil {
		return fmt.Errorf("enable platform bypass: %w", err)
	}
	fnErr := fn()
	if _, err := c.Exec(ctx, `SET LOCAL app.platform_bypass = 'false'`); err != nil {
		if fnErr != nil {
			return fnErr
		}
		return fmt.Errorf("disable platform bypass: %w", err)
	}
	return fnErr
}

// reserveCapacity atomically decrements available_capacity by quantity iff
// the offer is still active and has enough left -- a single conditional
// UPDATE, so concurrent placement attempts race safely at the row-lock
// level rather than needing an explicit SELECT ... FOR UPDATE. Zero rows
// affected means the offer lost the race (or was paused/withdrawn) since
// it was last read; the caller falls through to the next-ranked candidate.
func reserveCapacity(ctx context.Context, c conn, offerID uuid.UUID, quantity int) (pricePerUnitHour float64, ok bool, err error) {
	err = withPlatformBypass(ctx, c, func() error {
		return c.QueryRow(ctx, `
			UPDATE capacity_offers
			SET available_capacity = available_capacity - $2, updated_at = now()
			WHERE id = $1 AND status = 'active' AND available_capacity >= $2
			RETURNING price_per_unit_hour
		`, offerID, quantity).Scan(&pricePerUnitHour)
	})
	if err != nil {
		if err == pgx.ErrNoRows {
			return 0, false, nil
		}
		return 0, false, fmt.Errorf("reserve capacity: %w", err)
	}
	return pricePerUnitHour, true, nil
}

// releaseCapacity returns quantity to an offer's available_capacity,
// clamped so a bug elsewhere can never inflate available_capacity past
// total_capacity.
func releaseCapacity(ctx context.Context, c conn, offerID uuid.UUID, quantity int) error {
	err := withPlatformBypass(ctx, c, func() error {
		_, err := c.Exec(ctx, `
			UPDATE capacity_offers
			SET available_capacity = LEAST(available_capacity + $2, total_capacity), updated_at = now()
			WHERE id = $1
		`, offerID, quantity)
		return err
	})
	if err != nil {
		return fmt.Errorf("release capacity: %w", err)
	}
	return nil
}

// reclaimExpired lazily sweeps 'held' reservations whose expires_at has
// passed, marking them 'expired' and returning their quantity to the
// parent offer in one round trip. There is no scheduler/cron in this
// codebase yet to do this proactively -- every entry point into this
// package calls it first, so an expired hold is reclaimed the next time
// anyone reads or writes capacity, not on a fixed cadence. This is a
// documented known limitation, not a silent gap.
func reclaimExpired(ctx context.Context, c conn) error {
	err := withPlatformBypass(ctx, c, func() error {
		_, err := c.Exec(ctx, `
			WITH expired AS (
				UPDATE capacity_reservations
				SET status = 'expired', released_at = now(), release_reason = 'expired: hold not committed before expiry'
				WHERE status = 'held' AND expires_at < now()
				RETURNING capacity_offer_id, quantity
			), grouped AS (
				SELECT capacity_offer_id, SUM(quantity) AS qty FROM expired GROUP BY capacity_offer_id
			)
			UPDATE capacity_offers co
			SET available_capacity = LEAST(co.available_capacity + g.qty, co.total_capacity), updated_at = now()
			FROM grouped g
			WHERE co.id = g.capacity_offer_id
		`)
		return err
	})
	if err != nil {
		return fmt.Errorf("reclaim expired reservations: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Reservations
// ---------------------------------------------------------------------

const reservationColumns = `id, enterprise_tenant_id, operator_id, placement_request_id, capacity_offer_id, quantity,
	price_per_unit_hour, estimated_cost, status, approval_required, requested_by, approved_by,
	held_at, expires_at, committed_at, released_at, COALESCE(release_reason, '')`

func scanReservation(row pgx.Row) (Reservation, error) {
	var res Reservation
	err := row.Scan(&res.ID, &res.EnterpriseTenantID, &res.OperatorID, &res.PlacementRequestID, &res.CapacityOfferID,
		&res.Quantity, &res.PricePerUnitHour, &res.EstimatedCost, &res.Status, &res.ApprovalRequired,
		&res.RequestedBy, &res.ApprovedBy, &res.HeldAt, &res.ExpiresAt, &res.CommittedAt, &res.ReleasedAt, &res.ReleaseReason)
	if err != nil {
		return Reservation{}, err
	}
	return res, nil
}

func createReservation(ctx context.Context, c conn, tenantID, operatorID, requestID, offerID uuid.UUID, quantity int, pricePerUnitHour, estimatedCost float64, approvalRequired bool, requestedBy uuid.UUID, expiresAt time.Time) (Reservation, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO capacity_reservations (
			enterprise_tenant_id, operator_id, placement_request_id, capacity_offer_id, quantity,
			price_per_unit_hour, estimated_cost, approval_required, requested_by, expires_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING `+reservationColumns, tenantID, operatorID, requestID, offerID, quantity, pricePerUnitHour, estimatedCost,
		approvalRequired, requestedBy, expiresAt)
	res, err := scanReservation(row)
	if err != nil {
		return Reservation{}, fmt.Errorf("insert capacity reservation: %w", err)
	}
	return res, nil
}

func getReservationByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (Reservation, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+reservationColumns+` FROM capacity_reservations WHERE id = $1 AND enterprise_tenant_id = $2`, id, tenantID)
	res, err := scanReservation(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Reservation{}, false, nil
		}
		return Reservation{}, false, fmt.Errorf("get capacity reservation: %w", err)
	}
	return res, true, nil
}

func listReservationsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]Reservation, error) {
	rows, err := c.Query(ctx, `SELECT `+reservationColumns+` FROM capacity_reservations WHERE enterprise_tenant_id = $1 ORDER BY held_at DESC`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list capacity reservations: %w", err)
	}
	defer rows.Close()

	var out []Reservation
	for rows.Next() {
		res, err := scanReservation(rows)
		if err != nil {
			return nil, fmt.Errorf("scan capacity reservation: %w", err)
		}
		out = append(out, res)
	}
	return out, rows.Err()
}

// markCommitted transitions a 'held' reservation to 'committed'. approvedBy
// is nil when the workload version did not require approval (the same
// user who created the hold may commit it directly).
func markCommitted(ctx context.Context, c conn, id uuid.UUID, approvedBy *uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE capacity_reservations
		SET status = 'committed', approved_by = $2, committed_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'held'
	`, id, approvedBy)
	if err != nil {
		return false, fmt.Errorf("commit capacity reservation: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markReleased(ctx context.Context, c conn, id uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE capacity_reservations
		SET status = 'released', released_at = now(), release_reason = $2, updated_at = now()
		WHERE id = $1 AND status IN ('held', 'committed')
	`, id, reason)
	if err != nil {
		return false, fmt.Errorf("release capacity reservation: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}
