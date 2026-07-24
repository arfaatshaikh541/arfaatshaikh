package networkservices

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// conn is satisfied by both *pgxpool.Pool and pgx.Tx, matching the pattern
// every other module's repository layer uses.
type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// withPlatformBypass runs fn with app.platform_bypass set for the
// remainder of the current statement only -- used exactly like
// internal/modules/placement's helper of the same name, for the identical
// reason: network_service_offers' tenant-facing enterprise_read policy is
// SELECT-only, so reserving/releasing bandwidth from an enterprise-scoped
// transaction needs this narrow elevation, and resolving a network
// capability's cluster agent needs it too (cluster_agents has no
// tenant-facing policy at all -- see internal/modules/deployments' helper
// of the same name for the identical reasoning against that table).
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

// ---------------------------------------------------------------------
// Network service offers
// ---------------------------------------------------------------------

// networkCapabilityRegion looks up the region a network_capabilities row
// sits in (via its data centre or edge site) and confirms it belongs to
// operatorID in one round trip -- region_id is never accepted from the
// client, only derived server-side from a capability the operator actually
// owns. Mirrors internal/modules/capacityoffers' clusterRegion exactly.
func networkCapabilityRegion(ctx context.Context, c conn, capabilityID, operatorID uuid.UUID) (uuid.UUID, bool, error) {
	var regionID uuid.UUID
	err := c.QueryRow(ctx, `
		SELECT COALESCE(dc.region_id, es.region_id)
		FROM network_capabilities nc
		LEFT JOIN data_centres dc ON dc.id = nc.data_centre_id
		LEFT JOIN edge_sites es ON es.id = nc.edge_site_id
		WHERE nc.id = $1 AND nc.operator_id = $2
	`, capabilityID, operatorID).Scan(&regionID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("look up network capability region: %w", err)
	}
	return regionID, true, nil
}

const offerColumns = `id, operator_id, network_capability_id, region_id, service_class, total_bandwidth_gbps,
	available_bandwidth_gbps, max_latency_ms, price_per_unit_hour, currency, status, created_by, created_at, updated_at`

func scanOffer(row pgx.Row) (NetworkServiceOffer, error) {
	var o NetworkServiceOffer
	err := row.Scan(&o.ID, &o.OperatorID, &o.NetworkCapabilityID, &o.RegionID, &o.ServiceClass, &o.TotalBandwidthGbps,
		&o.AvailableBandwidthGbps, &o.MaxLatencyMs, &o.PricePerUnitHour, &o.Currency, &o.Status, &o.CreatedBy,
		&o.CreatedAt, &o.UpdatedAt)
	return o, err
}

func createOffer(ctx context.Context, c conn, operatorID, regionID, createdBy uuid.UUID, in CreateOfferInput) (NetworkServiceOffer, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO network_service_offers (
			operator_id, network_capability_id, region_id, service_class, total_bandwidth_gbps,
			available_bandwidth_gbps, max_latency_ms, price_per_unit_hour, currency, created_by
		) VALUES ($1, $2, $3, $4, $5, $5, $6, $7, $8, $9)
		RETURNING `+offerColumns, operatorID, in.NetworkCapabilityID, regionID, in.ServiceClass, in.TotalBandwidthGbps,
		in.MaxLatencyMs, in.PricePerUnitHour, in.Currency, createdBy)
	o, err := scanOffer(row)
	if err != nil {
		return NetworkServiceOffer{}, fmt.Errorf("insert network service offer: %w", err)
	}
	return o, nil
}

func listOffersForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]NetworkServiceOffer, error) {
	rows, err := c.Query(ctx, `SELECT `+offerColumns+` FROM network_service_offers WHERE operator_id = $1 ORDER BY created_at DESC`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list network service offers: %w", err)
	}
	defer rows.Close()
	out := []NetworkServiceOffer{}
	for rows.Next() {
		o, err := scanOffer(rows)
		if err != nil {
			return nil, fmt.Errorf("scan network service offer: %w", err)
		}
		out = append(out, o)
	}
	return out, rows.Err()
}

func getOfferByID(ctx context.Context, c conn, operatorID, id uuid.UUID) (NetworkServiceOffer, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+offerColumns+` FROM network_service_offers WHERE id = $1 AND operator_id = $2`, id, operatorID)
	o, err := scanOffer(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return NetworkServiceOffer{}, false, nil
		}
		return NetworkServiceOffer{}, false, fmt.Errorf("get network service offer: %w", err)
	}
	return o, true, nil
}

func updateOffer(ctx context.Context, c conn, operatorID, id uuid.UUID, in UpdateOfferInput) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE network_service_offers SET
			available_bandwidth_gbps = COALESCE($3, available_bandwidth_gbps),
			price_per_unit_hour = COALESCE($4, price_per_unit_hour),
			status = COALESCE($5, status),
			updated_at = now()
		WHERE id = $1 AND operator_id = $2
	`, id, operatorID, in.AvailableBandwidthGbps, in.PricePerUnitHour, in.Status)
	if err != nil {
		return false, fmt.Errorf("update network service offer: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func listActiveOffers(ctx context.Context, c conn) ([]OfferSummary, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, region_id, service_class, available_bandwidth_gbps, max_latency_ms, price_per_unit_hour, currency
		FROM network_service_offers WHERE status = 'active' ORDER BY id
	`)
	if err != nil {
		return nil, fmt.Errorf("list active network service offers: %w", err)
	}
	defer rows.Close()
	out := []OfferSummary{}
	for rows.Next() {
		var o OfferSummary
		if err := rows.Scan(&o.ID, &o.OperatorID, &o.RegionID, &o.ServiceClass, &o.AvailableBandwidthGbps, &o.MaxLatencyMs, &o.PricePerUnitHour, &o.Currency); err != nil {
			return nil, fmt.Errorf("scan network service offer: %w", err)
		}
		out = append(out, o)
	}
	return out, rows.Err()
}

// reserveBandwidth atomically decrements available_bandwidth_gbps by
// quantity iff the offer is still active and has enough left -- the same
// single-conditional-UPDATE concurrency-safety internal/modules/placement's
// reserveCapacity uses.
func reserveBandwidth(ctx context.Context, c conn, offerID uuid.UUID, bandwidthGbps float64) (pricePerUnitHour float64, ok bool, err error) {
	err = withPlatformBypass(ctx, c, func() error {
		return c.QueryRow(ctx, `
			UPDATE network_service_offers
			SET available_bandwidth_gbps = available_bandwidth_gbps - $2, updated_at = now()
			WHERE id = $1 AND status = 'active' AND available_bandwidth_gbps >= $2
			RETURNING price_per_unit_hour
		`, offerID, bandwidthGbps).Scan(&pricePerUnitHour)
	})
	if err != nil {
		if err == pgx.ErrNoRows {
			return 0, false, nil
		}
		return 0, false, fmt.Errorf("reserve bandwidth: %w", err)
	}
	return pricePerUnitHour, true, nil
}

func releaseBandwidth(ctx context.Context, c conn, offerID uuid.UUID, bandwidthGbps float64) error {
	err := withPlatformBypass(ctx, c, func() error {
		_, err := c.Exec(ctx, `
			UPDATE network_service_offers
			SET available_bandwidth_gbps = LEAST(available_bandwidth_gbps + $2, total_bandwidth_gbps), updated_at = now()
			WHERE id = $1
		`, offerID, bandwidthGbps)
		return err
	})
	if err != nil {
		return fmt.Errorf("release bandwidth: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Network service requests
// ---------------------------------------------------------------------

func createRequest(ctx context.Context, c conn, tenantID uuid.UUID, deploymentID *uuid.UUID, requiredBandwidthGbps float64, maxLatencyMs *float64, serviceClass *string, simulate bool, requestedBy uuid.UUID) (NetworkServiceRequest, error) {
	var req NetworkServiceRequest
	err := c.QueryRow(ctx, `
		INSERT INTO network_service_requests (enterprise_tenant_id, deployment_id, required_bandwidth_gbps, max_latency_ms, service_class, simulate, requested_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, enterprise_tenant_id, deployment_id, required_bandwidth_gbps, max_latency_ms, service_class, simulate, status, requested_by, created_at, updated_at
	`, tenantID, deploymentID, requiredBandwidthGbps, maxLatencyMs, serviceClass, simulate, requestedBy).Scan(
		&req.ID, &req.EnterpriseTenantID, &req.DeploymentID, &req.RequiredBandwidthGbps, &req.MaxLatencyMs,
		&req.ServiceClass, &req.Simulate, &req.Status, &req.RequestedBy, &req.CreatedAt, &req.UpdatedAt)
	if err != nil {
		return NetworkServiceRequest{}, fmt.Errorf("insert network service request: %w", err)
	}
	return req, nil
}

func markRequestStatus(ctx context.Context, c conn, id uuid.UUID, status string) error {
	_, err := c.Exec(ctx, `UPDATE network_service_requests SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("update network service request status: %w", err)
	}
	return nil
}

func listRequestsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]NetworkServiceRequest, error) {
	rows, err := c.Query(ctx, `
		SELECT id, enterprise_tenant_id, deployment_id, required_bandwidth_gbps, max_latency_ms, service_class, simulate, status, requested_by, created_at, updated_at
		FROM network_service_requests WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list network service requests: %w", err)
	}
	defer rows.Close()
	out := []NetworkServiceRequest{}
	for rows.Next() {
		var req NetworkServiceRequest
		if err := rows.Scan(&req.ID, &req.EnterpriseTenantID, &req.DeploymentID, &req.RequiredBandwidthGbps, &req.MaxLatencyMs,
			&req.ServiceClass, &req.Simulate, &req.Status, &req.RequestedBy, &req.CreatedAt, &req.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scan network service request: %w", err)
		}
		out = append(out, req)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Evaluations
// ---------------------------------------------------------------------

func insertEvaluation(ctx context.Context, c conn, tenantID, requestID, offerID, operatorID, regionID uuid.UUID, serviceClass, decision string, estimatedCost float64, reasonCodes []string, explanation map[string]any) (NetworkServiceEvaluation, error) {
	reasonCodesJSON, err := json.Marshal(reasonCodes)
	if err != nil {
		return NetworkServiceEvaluation{}, fmt.Errorf("encode reason codes: %w", err)
	}
	explanationJSON, err := json.Marshal(explanation)
	if err != nil {
		return NetworkServiceEvaluation{}, fmt.Errorf("encode explanation: %w", err)
	}
	var e NetworkServiceEvaluation
	var reasonRaw, explanationRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO network_service_evaluations (
			enterprise_tenant_id, network_service_request_id, network_service_offer_id, operator_id, region_id,
			service_class, decision, estimated_cost, reason_codes, explanation
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id, network_service_request_id, network_service_offer_id, operator_id, region_id, service_class,
			decision, rank, estimated_cost, reason_codes, explanation, created_at
	`, tenantID, requestID, offerID, operatorID, regionID, serviceClass, decision, estimatedCost, reasonCodesJSON, explanationJSON).Scan(
		&e.ID, &e.NetworkServiceRequestID, &e.NetworkServiceOfferID, &e.OperatorID, &e.RegionID, &e.ServiceClass,
		&e.Decision, &e.Rank, &e.EstimatedCost, &reasonRaw, &explanationRaw, &e.CreatedAt)
	if err != nil {
		return NetworkServiceEvaluation{}, fmt.Errorf("insert network service evaluation: %w", err)
	}
	if err := json.Unmarshal(reasonRaw, &e.ReasonCodes); err != nil {
		return NetworkServiceEvaluation{}, fmt.Errorf("decode reason codes: %w", err)
	}
	if err := json.Unmarshal(explanationRaw, &e.Explanation); err != nil {
		return NetworkServiceEvaluation{}, fmt.Errorf("decode explanation: %w", err)
	}
	return e, nil
}

func setEvaluationRank(ctx context.Context, c conn, id uuid.UUID, rank int) error {
	_, err := c.Exec(ctx, `UPDATE network_service_evaluations SET rank = $2 WHERE id = $1`, id, rank)
	if err != nil {
		return fmt.Errorf("set evaluation rank: %w", err)
	}
	return nil
}

func listEvaluationsForRequest(ctx context.Context, c conn, tenantID, requestID uuid.UUID) ([]NetworkServiceEvaluation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, network_service_request_id, network_service_offer_id, operator_id, region_id, service_class,
			decision, rank, estimated_cost, reason_codes, explanation, created_at
		FROM network_service_evaluations WHERE enterprise_tenant_id = $1 AND network_service_request_id = $2
		ORDER BY (rank IS NULL), rank, estimated_cost
	`, tenantID, requestID)
	if err != nil {
		return nil, fmt.Errorf("list network service evaluations: %w", err)
	}
	defer rows.Close()
	out := []NetworkServiceEvaluation{}
	for rows.Next() {
		var e NetworkServiceEvaluation
		var reasonRaw, explanationRaw []byte
		if err := rows.Scan(&e.ID, &e.NetworkServiceRequestID, &e.NetworkServiceOfferID, &e.OperatorID, &e.RegionID, &e.ServiceClass,
			&e.Decision, &e.Rank, &e.EstimatedCost, &reasonRaw, &explanationRaw, &e.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan network service evaluation: %w", err)
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
// Reservations
// ---------------------------------------------------------------------

const reservationColumns = `id, enterprise_tenant_id, operator_id, network_service_request_id, network_service_offer_id,
	deployment_id, cluster_agent_id, bandwidth_gbps, price_per_unit_hour, estimated_cost, status, provisioning_status,
	requested_by, committed_at, released_at, COALESCE(release_reason, '')`

func scanReservation(row pgx.Row) (NetworkReservation, error) {
	var res NetworkReservation
	err := row.Scan(&res.ID, &res.EnterpriseTenantID, &res.OperatorID, &res.NetworkServiceRequestID, &res.NetworkServiceOfferID,
		&res.DeploymentID, &res.ClusterAgentID, &res.BandwidthGbps, &res.PricePerUnitHour, &res.EstimatedCost, &res.Status,
		&res.ProvisioningStatus, &res.RequestedBy, &res.CommittedAt, &res.ReleasedAt, &res.ReleaseReason)
	return res, err
}

func createReservation(ctx context.Context, c conn, tenantID, operatorID, requestID, offerID uuid.UUID, deploymentID, clusterAgentID *uuid.UUID, bandwidthGbps, pricePerUnitHour, estimatedCost float64, requestedBy uuid.UUID) (NetworkReservation, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO network_reservations (
			enterprise_tenant_id, operator_id, network_service_request_id, network_service_offer_id, deployment_id,
			cluster_agent_id, bandwidth_gbps, price_per_unit_hour, estimated_cost, requested_by
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING `+reservationColumns, tenantID, operatorID, requestID, offerID, deploymentID, clusterAgentID,
		bandwidthGbps, pricePerUnitHour, estimatedCost, requestedBy)
	res, err := scanReservation(row)
	if err != nil {
		return NetworkReservation{}, fmt.Errorf("insert network reservation: %w", err)
	}
	return res, nil
}

func getReservationByIDForTenant(ctx context.Context, c conn, tenantID, id uuid.UUID) (NetworkReservation, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+reservationColumns+` FROM network_reservations WHERE id = $1 AND enterprise_tenant_id = $2`, id, tenantID)
	res, err := scanReservation(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return NetworkReservation{}, false, nil
		}
		return NetworkReservation{}, false, fmt.Errorf("get network reservation: %w", err)
	}
	return res, true, nil
}

// getReservationByIDAnyScope looks a reservation up by id alone -- used
// only by machine-authenticated agent-facing paths.
func getReservationByIDAnyScope(ctx context.Context, c conn, id uuid.UUID) (NetworkReservation, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+reservationColumns+` FROM network_reservations WHERE id = $1`, id)
	res, err := scanReservation(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return NetworkReservation{}, false, nil
		}
		return NetworkReservation{}, false, fmt.Errorf("get network reservation (any scope): %w", err)
	}
	return res, true, nil
}

func listReservationsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]NetworkReservation, error) {
	rows, err := c.Query(ctx, `SELECT `+reservationColumns+` FROM network_reservations WHERE enterprise_tenant_id = $1 ORDER BY committed_at DESC`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list network reservations: %w", err)
	}
	defer rows.Close()
	out := []NetworkReservation{}
	for rows.Next() {
		res, err := scanReservation(rows)
		if err != nil {
			return nil, fmt.Errorf("scan network reservation: %w", err)
		}
		out = append(out, res)
	}
	return out, rows.Err()
}

func listReservationsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]NetworkReservation, error) {
	rows, err := c.Query(ctx, `SELECT `+reservationColumns+` FROM network_reservations WHERE operator_id = $1 ORDER BY committed_at DESC`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list network reservations for operator: %w", err)
	}
	defer rows.Close()
	out := []NetworkReservation{}
	for rows.Next() {
		res, err := scanReservation(rows)
		if err != nil {
			return nil, fmt.Errorf("scan network reservation: %w", err)
		}
		out = append(out, res)
	}
	return out, rows.Err()
}

func markReservationReleased(ctx context.Context, c conn, id uuid.UUID, reason string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE network_reservations SET status = 'released', released_at = now(), release_reason = $2, updated_at = now()
		WHERE id = $1 AND status = 'committed'
	`, id, reason)
	if err != nil {
		return false, fmt.Errorf("release network reservation: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func setProvisioningStatus(ctx context.Context, c conn, id uuid.UUID, status string) error {
	_, err := c.Exec(ctx, `UPDATE network_reservations SET provisioning_status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("set network reservation provisioning status: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Network health events (append-only)
// ---------------------------------------------------------------------

func insertHealthEvent(ctx context.Context, c conn, operatorID uuid.UUID, tenantID, reservationID *uuid.UUID, eventType, severity string, detail map[string]any, occurredAt time.Time) (NetworkHealthEvent, error) {
	detailJSON, err := json.Marshal(detail)
	if err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("encode event detail: %w", err)
	}
	var e NetworkHealthEvent
	var detailRaw []byte
	err = c.QueryRow(ctx, `
		INSERT INTO network_health_events (operator_id, enterprise_tenant_id, network_reservation_id, event_type, severity, detail, occurred_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, operator_id, enterprise_tenant_id, network_reservation_id, event_type, severity, detail, occurred_at, created_at
	`, operatorID, tenantID, reservationID, eventType, severity, detailJSON, occurredAt).Scan(
		&e.ID, &e.OperatorID, &e.EnterpriseTenantID, &e.NetworkReservationID, &e.EventType, &e.Severity, &detailRaw, &e.OccurredAt, &e.CreatedAt)
	if err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("insert network health event: %w", err)
	}
	if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
		return NetworkHealthEvent{}, fmt.Errorf("decode event detail: %w", err)
	}
	return e, nil
}

func listHealthEventsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]NetworkHealthEvent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, enterprise_tenant_id, network_reservation_id, event_type, severity, detail, occurred_at, created_at
		FROM network_health_events WHERE operator_id = $1 ORDER BY occurred_at DESC LIMIT 200
	`, operatorID)
	return scanHealthEvents(rows, err)
}

func listHealthEventsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]NetworkHealthEvent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, enterprise_tenant_id, network_reservation_id, event_type, severity, detail, occurred_at, created_at
		FROM network_health_events WHERE enterprise_tenant_id = $1 ORDER BY occurred_at DESC LIMIT 200
	`, tenantID)
	return scanHealthEvents(rows, err)
}

func scanHealthEvents(rows pgx.Rows, err error) ([]NetworkHealthEvent, error) {
	if err != nil {
		return nil, fmt.Errorf("list network health events: %w", err)
	}
	defer rows.Close()
	out := []NetworkHealthEvent{}
	for rows.Next() {
		var e NetworkHealthEvent
		var detailRaw []byte
		if err := rows.Scan(&e.ID, &e.OperatorID, &e.EnterpriseTenantID, &e.NetworkReservationID, &e.EventType, &e.Severity, &detailRaw, &e.OccurredAt, &e.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan network health event: %w", err)
		}
		if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
			return nil, fmt.Errorf("decode event detail: %w", err)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Cross-module reads: network_capabilities -> location -> clusters ->
// cluster_agents, deployments. Each of these tables is owned by another
// module; this package only ever reads them directly by SQL, the same
// "each module owns its own SQL against shared tables" convention
// internal/modules/placement and internal/modules/deployments already
// established.
// ---------------------------------------------------------------------

// activeClusterAgentForCapability resolves the active cluster agent for
// whichever cluster shares a data centre or edge site with a network
// capability -- there is no direct network_capability -> cluster_agent
// link, so this joins through the shared location, picking the
// most-recently-registered active agent if more than one cluster exists at
// that location. Requires platform_bypass (cluster_agents has no
// tenant-facing RLS policy).
func activeClusterAgentForCapability(ctx context.Context, c conn, capabilityID uuid.UUID) (uuid.UUID, bool, error) {
	var agentID uuid.UUID
	err := c.QueryRow(ctx, `
		SELECT ca.id
		FROM network_capabilities nc
		JOIN clusters cl ON (cl.data_centre_id = nc.data_centre_id AND nc.data_centre_id IS NOT NULL)
			OR (cl.edge_site_id = nc.edge_site_id AND nc.edge_site_id IS NOT NULL)
		JOIN cluster_agents ca ON ca.cluster_id = cl.id AND ca.status = 'active'
		WHERE nc.id = $1
		ORDER BY ca.created_at DESC LIMIT 1
	`, capabilityID).Scan(&agentID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("resolve active cluster agent for network capability: %w", err)
	}
	return agentID, true, nil
}

// activeClusterAgentForOffer resolves the active cluster agent for the
// network capability backing a given offer -- the entry point
// EvaluateAndReserve actually has (an offer ID, not a capability ID)
// before delegating to activeClusterAgentForCapability.
func activeClusterAgentForOffer(ctx context.Context, c conn, offerID uuid.UUID) (uuid.UUID, bool, error) {
	var capabilityID uuid.UUID
	err := c.QueryRow(ctx, `SELECT network_capability_id FROM network_service_offers WHERE id = $1`, offerID).Scan(&capabilityID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("look up network service offer capability: %w", err)
	}
	return activeClusterAgentForCapability(ctx, c, capabilityID)
}

// clusterAgentIdentity resolves the owning operator and current valid
// certificate PEM for a cluster agent -- duplicated from the same-named
// helpers in internal/modules/agents/internal/modules/deployments/internal/modules/attestation
// rather than shared, per this codebase's established convention of small
// per-consumer primitives.
func clusterAgentIdentity(ctx context.Context, c conn, agentID uuid.UUID) (operatorID uuid.UUID, certPEM string, ok bool, err error) {
	err = c.QueryRow(ctx, `SELECT operator_id FROM cluster_agents WHERE id = $1 AND status = 'active'`, agentID).Scan(&operatorID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, "", false, nil
		}
		return uuid.Nil, "", false, fmt.Errorf("resolve cluster agent operator: %w", err)
	}
	err = c.QueryRow(ctx, `
		SELECT certificate_pem FROM cluster_agent_certificates
		WHERE cluster_agent_id = $1 AND revoked_at IS NULL AND expires_at > now()
		ORDER BY issued_at DESC LIMIT 1
	`, agentID).Scan(&certPEM)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, "", false, nil
		}
		return uuid.Nil, "", false, fmt.Errorf("load current cluster agent certificate: %w", err)
	}
	return operatorID, certPEM, true, nil
}

// ---------------------------------------------------------------------
// Control messages (write-only from this package's perspective, exactly
// mirroring internal/modules/deployments' equivalent section)
// ---------------------------------------------------------------------

func createControlMessage(ctx context.Context, c conn, operatorID, agentID uuid.UUID, direction, messageType string, inResponseTo *uuid.UUID, nonce string, payload []byte, signature string, signedAt time.Time, status string) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `
		INSERT INTO control_messages (operator_id, cluster_agent_id, direction, message_type, in_response_to, nonce, payload, signature, signed_at, status)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id
	`, operatorID, agentID, direction, messageType, inResponseTo, nonce, string(payload), signature, signedAt, status).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("insert control message: %w", err)
	}
	return id, nil
}

func controlMessageNonceExists(ctx context.Context, c conn, agentID uuid.UUID, nonce string) (bool, error) {
	var exists bool
	err := c.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM control_messages WHERE cluster_agent_id = $1 AND nonce = $2)`, agentID, nonce).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check control message nonce: %w", err)
	}
	return exists, nil
}

func getPendingProvisionMessage(ctx context.Context, c conn, agentID, messageID uuid.UUID) (networkProvisionPayload, bool, error) {
	var payloadRaw string
	err := c.QueryRow(ctx, `
		SELECT payload FROM control_messages
		WHERE id = $1 AND cluster_agent_id = $2 AND direction = 'to_agent' AND message_type = 'network_service_provision' AND status = 'pending'
	`, messageID, agentID).Scan(&payloadRaw)
	if err != nil {
		if err == pgx.ErrNoRows {
			return networkProvisionPayload{}, false, nil
		}
		return networkProvisionPayload{}, false, fmt.Errorf("look up pending network provision message: %w", err)
	}
	var payload networkProvisionPayload
	if err := json.Unmarshal([]byte(payloadRaw), &payload); err != nil {
		return networkProvisionPayload{}, false, fmt.Errorf("decode network provision payload: %w", err)
	}
	return payload, true, nil
}

func markControlMessageResponded(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE control_messages SET status = 'responded' WHERE id = $1 AND status = 'pending'`, id)
	if err != nil {
		return false, fmt.Errorf("mark control message responded: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}
