package capacityoffers

import (
	"context"
	"fmt"

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

// clusterRegion looks up the region a cluster sits in (via its data centre
// or edge site) and confirms the cluster belongs to operatorID in one
// round trip -- region_id is never accepted from the client, only derived
// server-side from the cluster the operator actually owns.
func clusterRegion(ctx context.Context, c conn, clusterID, operatorID uuid.UUID) (uuid.UUID, bool, error) {
	var regionID uuid.UUID
	err := c.QueryRow(ctx, `
		SELECT COALESCE(dc.region_id, es.region_id)
		FROM clusters cl
		LEFT JOIN data_centres dc ON dc.id = cl.data_centre_id
		LEFT JOIN edge_sites es ON es.id = cl.edge_site_id
		WHERE cl.id = $1 AND cl.operator_id = $2
	`, clusterID, operatorID).Scan(&regionID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("look up cluster region: %w", err)
	}
	return regionID, true, nil
}

const offerColumns = `id, operator_id, cluster_id, region_id, accelerator_type, total_capacity, available_capacity,
	price_per_unit_hour, currency, confidential_computing_available, estimated_kwh_per_unit_hour, status,
	created_by, created_at, updated_at`

func scanOffer(row pgx.Row) (CapacityOffer, error) {
	var o CapacityOffer
	err := row.Scan(&o.ID, &o.OperatorID, &o.ClusterID, &o.RegionID, &o.AcceleratorType, &o.TotalCapacity,
		&o.AvailableCapacity, &o.PricePerUnitHour, &o.Currency, &o.ConfidentialComputingAvailable,
		&o.EstimatedKWhPerUnitHour, &o.Status, &o.CreatedBy, &o.CreatedAt, &o.UpdatedAt)
	if err != nil {
		return CapacityOffer{}, err
	}
	return o, nil
}

func createOffer(ctx context.Context, c conn, operatorID, regionID, createdBy uuid.UUID, in CreateOfferInput) (CapacityOffer, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO capacity_offers (
			operator_id, cluster_id, region_id, accelerator_type, total_capacity, available_capacity,
			price_per_unit_hour, currency, confidential_computing_available, estimated_kwh_per_unit_hour, created_by
		) VALUES ($1, $2, $3, $4, $5, $5, $6, $7, $8, $9, $10)
		RETURNING `+offerColumns, operatorID, in.ClusterID, regionID, in.AcceleratorType, in.TotalCapacity,
		in.PricePerUnitHour, in.Currency, in.ConfidentialComputingAvailable, in.EstimatedKWhPerUnitHour, createdBy)
	o, err := scanOffer(row)
	if err != nil {
		return CapacityOffer{}, fmt.Errorf("insert capacity offer: %w", err)
	}
	return o, nil
}

func listOffers(ctx context.Context, c conn, operatorID uuid.UUID) ([]CapacityOffer, error) {
	rows, err := c.Query(ctx, `SELECT `+offerColumns+` FROM capacity_offers WHERE operator_id = $1 ORDER BY created_at DESC`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list capacity offers: %w", err)
	}
	defer rows.Close()

	var out []CapacityOffer
	for rows.Next() {
		o, err := scanOffer(rows)
		if err != nil {
			return nil, fmt.Errorf("scan capacity offer: %w", err)
		}
		out = append(out, o)
	}
	return out, rows.Err()
}

func getOfferByID(ctx context.Context, c conn, operatorID, id uuid.UUID) (CapacityOffer, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+offerColumns+` FROM capacity_offers WHERE id = $1 AND operator_id = $2`, id, operatorID)
	o, err := scanOffer(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return CapacityOffer{}, false, nil
		}
		return CapacityOffer{}, false, fmt.Errorf("get capacity offer: %w", err)
	}
	return o, true, nil
}

// updateOffer applies whichever fields are set in in. Manually raising
// available_capacity is how an operator adds new supply to an existing
// offer -- it does not interact with in-flight reservations, which are
// tracked and released only by the placement package's atomic
// reserve/release statements. An operator who manually lowers
// available_capacity below what is already held is a pricing/supply
// decision the CHECK constraint (available_capacity <= total_capacity)
// still enforces, but this codebase does not attempt to reconcile it
// against outstanding holds -- a known limitation recorded in
// docs/project-status.md.
func updateOffer(ctx context.Context, c conn, operatorID, id uuid.UUID, in UpdateOfferInput) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE capacity_offers SET
			available_capacity = COALESCE($3, available_capacity),
			price_per_unit_hour = COALESCE($4, price_per_unit_hour),
			status = COALESCE($5, status),
			updated_at = now()
		WHERE id = $1 AND operator_id = $2
	`, id, operatorID, in.AvailableCapacity, in.PricePerUnitHour, in.Status)
	if err != nil {
		return false, fmt.Errorf("update capacity offer: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

const reservationColumns = `id, enterprise_tenant_id, placement_request_id, capacity_offer_id, quantity,
	price_per_unit_hour, estimated_cost, status, approval_required, requested_by, approved_by,
	held_at, expires_at, committed_at, released_at`

func scanReservation(row pgx.Row) (Reservation, error) {
	var res Reservation
	err := row.Scan(&res.ID, &res.EnterpriseTenantID, &res.PlacementRequestID, &res.CapacityOfferID, &res.Quantity,
		&res.PricePerUnitHour, &res.EstimatedCost, &res.Status, &res.ApprovalRequired, &res.RequestedBy, &res.ApprovedBy,
		&res.HeldAt, &res.ExpiresAt, &res.CommittedAt, &res.ReleasedAt)
	if err != nil {
		return Reservation{}, err
	}
	return res, nil
}

func listReservationsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]Reservation, error) {
	rows, err := c.Query(ctx, `SELECT `+reservationColumns+` FROM capacity_reservations WHERE operator_id = $1 ORDER BY held_at DESC`, operatorID)
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
