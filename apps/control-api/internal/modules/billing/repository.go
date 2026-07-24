package billing

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// conn is satisfied by both *pgxpool.Pool and pgx.Tx, matching every other
// module's repository layer in this codebase.
type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// ---------------------------------------------------------------------
// Usage metrics (static catalog, no RLS -- like features/subscription_plans)
// ---------------------------------------------------------------------

func listUsageMetrics(ctx context.Context, c conn) ([]UsageMetric, error) {
	rows, err := c.Query(ctx, `SELECT key, name, unit, description FROM usage_metrics ORDER BY key`)
	if err != nil {
		return nil, fmt.Errorf("list usage metrics: %w", err)
	}
	defer rows.Close()
	out := []UsageMetric{}
	for rows.Next() {
		var m UsageMetric
		if err := rows.Scan(&m.Key, &m.Name, &m.Unit, &m.Description); err != nil {
			return nil, fmt.Errorf("scan usage metric: %w", err)
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Usage events
// ---------------------------------------------------------------------

// resolveDeploymentOwnership, resolveCapacityReservationOwnership, and
// resolveNetworkReservationOwnership each answer "which operator and
// tenant does this resource actually belong to" -- the server-side
// resolution AgentReportUsage uses instead of ever trusting an
// operator_id/enterprise_tenant_id claimed directly in a machine-signed
// payload. Each of these tables is owned by another module; this package
// only ever reads them directly by SQL, the same "each module owns its own
// SQL against shared tables" convention internal/modules/networkservices
// and internal/modules/assurance already established.
func resolveDeploymentOwnership(ctx context.Context, c conn, id uuid.UUID) (operatorID, tenantID uuid.UUID, ok bool, err error) {
	err = c.QueryRow(ctx, `SELECT operator_id, enterprise_tenant_id FROM deployments WHERE id = $1`, id).Scan(&operatorID, &tenantID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, uuid.Nil, false, nil
		}
		return uuid.Nil, uuid.Nil, false, fmt.Errorf("resolve deployment ownership: %w", err)
	}
	return operatorID, tenantID, true, nil
}

func resolveCapacityReservationOwnership(ctx context.Context, c conn, id uuid.UUID) (operatorID, tenantID uuid.UUID, ok bool, err error) {
	err = c.QueryRow(ctx, `SELECT operator_id, enterprise_tenant_id FROM capacity_reservations WHERE id = $1`, id).Scan(&operatorID, &tenantID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, uuid.Nil, false, nil
		}
		return uuid.Nil, uuid.Nil, false, fmt.Errorf("resolve capacity reservation ownership: %w", err)
	}
	return operatorID, tenantID, true, nil
}

func resolveNetworkReservationOwnership(ctx context.Context, c conn, id uuid.UUID) (operatorID, tenantID uuid.UUID, ok bool, err error) {
	err = c.QueryRow(ctx, `SELECT operator_id, enterprise_tenant_id FROM network_reservations WHERE id = $1`, id).Scan(&operatorID, &tenantID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, uuid.Nil, false, nil
		}
		return uuid.Nil, uuid.Nil, false, fmt.Errorf("resolve network reservation ownership: %w", err)
	}
	return operatorID, tenantID, true, nil
}

// bilateralAgreementTerms is what CreateSettlementForAgreement needs from a
// bilateral_agreements row -- read directly by SQL against a table
// internal/modules/capacityoffers owns writes to, the same "each module owns
// its own SQL against shared tables" convention this file already applies
// to deployments/capacity_reservations/network_reservations above.
type bilateralAgreementTerms struct {
	enterpriseTenantID uuid.UUID
	currency           string
	platformFeeRate    float64
	status             string
}

func getBilateralAgreementForOperator(ctx context.Context, c conn, operatorID, agreementID uuid.UUID) (bilateralAgreementTerms, bool, error) {
	var t bilateralAgreementTerms
	err := c.QueryRow(ctx, `
		SELECT enterprise_tenant_id, currency, platform_fee_rate, status
		FROM bilateral_agreements WHERE id = $1 AND operator_id = $2
	`, agreementID, operatorID).Scan(&t.enterpriseTenantID, &t.currency, &t.platformFeeRate, &t.status)
	if err != nil {
		if err == pgx.ErrNoRows {
			return bilateralAgreementTerms{}, false, nil
		}
		return bilateralAgreementTerms{}, false, fmt.Errorf("resolve bilateral agreement: %w", err)
	}
	return t, true, nil
}

// clusterAgentIdentity resolves the owning operator and current valid
// certificate PEM for a cluster agent -- duplicated from the same-named
// helpers in internal/modules/agents/deployments/attestation/networkservices
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

const usageEventColumns = `id, operator_id, enterprise_tenant_id, cluster_agent_id, deployment_id, capacity_reservation_id,
	network_reservation_id, usage_metric_key, quantity, occurred_at, created_at`

func scanUsageEvent(row pgx.Row) (UsageEvent, error) {
	var e UsageEvent
	err := row.Scan(&e.ID, &e.OperatorID, &e.EnterpriseTenantID, &e.ClusterAgentID, &e.DeploymentID, &e.CapacityReservationID,
		&e.NetworkReservationID, &e.UsageMetricKey, &e.Quantity, &e.OccurredAt, &e.CreatedAt)
	return e, err
}

// ErrDuplicateUsageEvent signals a unique_violation on (cluster_agent_id,
// nonce) -- the approved scope's "duplicate protection"/"idempotency"
// requirement, enforced at the database level (unlike every other nonce
// check in this codebase, which is a plain pre-insert SELECT) since usage
// events directly drive billing amounts and the correctness stakes are
// correspondingly higher than replaying a poll or command result.
var ErrDuplicateUsageEvent = errors.New("usage event nonce already used by this cluster agent")

func insertUsageEvent(ctx context.Context, c conn, operatorID, tenantID, clusterAgentID uuid.UUID, deploymentID, capacityReservationID, networkReservationID *uuid.UUID, metricKey string, quantity float64, occurredAt time.Time, nonce, signature string) (UsageEvent, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO usage_events (operator_id, enterprise_tenant_id, cluster_agent_id, deployment_id, capacity_reservation_id,
			network_reservation_id, usage_metric_key, quantity, occurred_at, nonce, signature)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		RETURNING `+usageEventColumns, operatorID, tenantID, clusterAgentID, deploymentID, capacityReservationID,
		networkReservationID, metricKey, quantity, occurredAt, nonce, signature)
	e, err := scanUsageEvent(row)
	if err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			return UsageEvent{}, ErrDuplicateUsageEvent
		}
		return UsageEvent{}, fmt.Errorf("insert usage event: %w", err)
	}
	return e, nil
}

func listUsageEventsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]UsageEvent, error) {
	rows, err := c.Query(ctx, `SELECT `+usageEventColumns+` FROM usage_events WHERE operator_id = $1 ORDER BY occurred_at DESC LIMIT 200`, operatorID)
	return scanUsageEvents(rows, err)
}

func listUsageEventsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]UsageEvent, error) {
	rows, err := c.Query(ctx, `SELECT `+usageEventColumns+` FROM usage_events WHERE enterprise_tenant_id = $1 ORDER BY occurred_at DESC LIMIT 200`, tenantID)
	return scanUsageEvents(rows, err)
}

func scanUsageEvents(rows pgx.Rows, err error) ([]UsageEvent, error) {
	if err != nil {
		return nil, fmt.Errorf("list usage events: %w", err)
	}
	defer rows.Close()
	out := []UsageEvent{}
	for rows.Next() {
		e, err := scanUsageEvent(rows)
		if err != nil {
			return nil, fmt.Errorf("scan usage event: %w", err)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Usage aggregation
// ---------------------------------------------------------------------

// aggregateUsage groups every usage_events row for one operator+tenant in
// [periodStart, periodEnd) by metric key and upserts one usage_aggregations
// row per metric -- idempotent re-running as more events land before the
// period closes, the same "recomputable rollup, not append-only evidence"
// design migration 0034's header comment documents.
func aggregateUsage(ctx context.Context, c conn, operatorID, tenantID uuid.UUID, periodStart, periodEnd time.Time) ([]UsageAggregation, error) {
	rows, err := c.Query(ctx, `
		SELECT usage_metric_key, COALESCE(SUM(quantity), 0), count(*)
		FROM usage_events
		WHERE operator_id = $1 AND enterprise_tenant_id = $2 AND occurred_at >= $3 AND occurred_at < $4
		GROUP BY usage_metric_key
	`, operatorID, tenantID, periodStart, periodEnd)
	if err != nil {
		return nil, fmt.Errorf("group usage events: %w", err)
	}
	type groupRow struct {
		metricKey     string
		totalQuantity float64
		eventCount    int
	}
	var groups []groupRow
	for rows.Next() {
		var g groupRow
		if err := rows.Scan(&g.metricKey, &g.totalQuantity, &g.eventCount); err != nil {
			rows.Close()
			return nil, fmt.Errorf("scan usage group: %w", err)
		}
		groups = append(groups, g)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return nil, err
	}
	rows.Close()

	out := make([]UsageAggregation, 0, len(groups))
	for _, g := range groups {
		var a UsageAggregation
		row := c.QueryRow(ctx, `
			INSERT INTO usage_aggregations (operator_id, enterprise_tenant_id, usage_metric_key, period_start, period_end, total_quantity, source_event_count)
			VALUES ($1, $2, $3, $4, $5, $6, $7)
			ON CONFLICT (operator_id, enterprise_tenant_id, usage_metric_key, period_start, period_end)
			DO UPDATE SET total_quantity = EXCLUDED.total_quantity, source_event_count = EXCLUDED.source_event_count, computed_at = now()
			RETURNING id, operator_id, enterprise_tenant_id, usage_metric_key, period_start, period_end, total_quantity, source_event_count, computed_at
		`, operatorID, tenantID, g.metricKey, periodStart, periodEnd, g.totalQuantity, g.eventCount)
		if err := row.Scan(&a.ID, &a.OperatorID, &a.EnterpriseTenantID, &a.UsageMetricKey, &a.PeriodStart, &a.PeriodEnd,
			&a.TotalQuantity, &a.SourceEventCount, &a.ComputedAt); err != nil {
			return nil, fmt.Errorf("upsert usage aggregation: %w", err)
		}
		out = append(out, a)
	}
	return out, nil
}

func getUsageAggregationsForPeriod(ctx context.Context, c conn, operatorID, tenantID uuid.UUID, periodStart, periodEnd time.Time) ([]UsageAggregation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, enterprise_tenant_id, usage_metric_key, period_start, period_end, total_quantity, source_event_count, computed_at
		FROM usage_aggregations WHERE operator_id = $1 AND enterprise_tenant_id = $2 AND period_start = $3 AND period_end = $4
	`, operatorID, tenantID, periodStart, periodEnd)
	if err != nil {
		return nil, fmt.Errorf("get usage aggregations for period: %w", err)
	}
	defer rows.Close()
	out := []UsageAggregation{}
	for rows.Next() {
		var a UsageAggregation
		if err := rows.Scan(&a.ID, &a.OperatorID, &a.EnterpriseTenantID, &a.UsageMetricKey, &a.PeriodStart, &a.PeriodEnd,
			&a.TotalQuantity, &a.SourceEventCount, &a.ComputedAt); err != nil {
			return nil, fmt.Errorf("scan usage aggregation: %w", err)
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func listUsageAggregationsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]UsageAggregation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, enterprise_tenant_id, usage_metric_key, period_start, period_end, total_quantity, source_event_count, computed_at
		FROM usage_aggregations WHERE operator_id = $1 ORDER BY period_start DESC LIMIT 200
	`, operatorID)
	return scanUsageAggregations(rows, err)
}

func listUsageAggregationsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]UsageAggregation, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, enterprise_tenant_id, usage_metric_key, period_start, period_end, total_quantity, source_event_count, computed_at
		FROM usage_aggregations WHERE enterprise_tenant_id = $1 ORDER BY period_start DESC LIMIT 200
	`, tenantID)
	return scanUsageAggregations(rows, err)
}

func scanUsageAggregations(rows pgx.Rows, err error) ([]UsageAggregation, error) {
	if err != nil {
		return nil, fmt.Errorf("list usage aggregations: %w", err)
	}
	defer rows.Close()
	out := []UsageAggregation{}
	for rows.Next() {
		var a UsageAggregation
		if err := rows.Scan(&a.ID, &a.OperatorID, &a.EnterpriseTenantID, &a.UsageMetricKey, &a.PeriodStart, &a.PeriodEnd,
			&a.TotalQuantity, &a.SourceEventCount, &a.ComputedAt); err != nil {
			return nil, fmt.Errorf("scan usage aggregation: %w", err)
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Price books and price rules
// ---------------------------------------------------------------------

func createPriceBook(ctx context.Context, c conn, operatorID *uuid.UUID, createdBy uuid.UUID, in CreatePriceBookInput) (PriceBook, error) {
	var nextVersion int
	if err := c.QueryRow(ctx, `SELECT COALESCE(MAX(version), 0) + 1 FROM price_books WHERE operator_id IS NOT DISTINCT FROM $1`, operatorID).Scan(&nextVersion); err != nil {
		return PriceBook{}, fmt.Errorf("resolve next price book version: %w", err)
	}
	var pb PriceBook
	row := c.QueryRow(ctx, `
		INSERT INTO price_books (operator_id, version, currency, created_by)
		VALUES ($1, $2, $3, $4)
		RETURNING id, operator_id, version, currency, status, created_by, created_at, activated_at
	`, operatorID, nextVersion, in.Currency, createdBy)
	if err := row.Scan(&pb.ID, &pb.OperatorID, &pb.Version, &pb.Currency, &pb.Status, &pb.CreatedBy, &pb.CreatedAt, &pb.ActivatedAt); err != nil {
		return PriceBook{}, fmt.Errorf("insert price book: %w", err)
	}
	for _, ruleIn := range in.Rules {
		var r PriceRule
		if err := c.QueryRow(ctx, `
			INSERT INTO price_rules (price_book_id, usage_metric_key, unit_price) VALUES ($1, $2, $3)
			RETURNING id, price_book_id, usage_metric_key, unit_price
		`, pb.ID, ruleIn.UsageMetricKey, ruleIn.UnitPrice).Scan(&r.ID, &r.PriceBookID, &r.UsageMetricKey, &r.UnitPrice); err != nil {
			return PriceBook{}, fmt.Errorf("insert price rule %q: %w", ruleIn.UsageMetricKey, err)
		}
		pb.Rules = append(pb.Rules, r)
	}
	return pb, nil
}

func listPriceBooksForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]PriceBook, error) {
	rows, err := c.Query(ctx, `
		SELECT id, operator_id, version, currency, status, created_by, created_at, activated_at
		FROM price_books WHERE operator_id = $1 ORDER BY version DESC
	`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list price books: %w", err)
	}
	defer rows.Close()
	out := []PriceBook{}
	for rows.Next() {
		var pb PriceBook
		if err := rows.Scan(&pb.ID, &pb.OperatorID, &pb.Version, &pb.Currency, &pb.Status, &pb.CreatedBy, &pb.CreatedAt, &pb.ActivatedAt); err != nil {
			return nil, fmt.Errorf("scan price book: %w", err)
		}
		out = append(out, pb)
	}
	return out, rows.Err()
}

func getPriceBookByIDOperator(ctx context.Context, c conn, operatorID, id uuid.UUID) (PriceBook, bool, error) {
	var pb PriceBook
	row := c.QueryRow(ctx, `
		SELECT id, operator_id, version, currency, status, created_by, created_at, activated_at
		FROM price_books WHERE id = $1 AND operator_id = $2
	`, id, operatorID)
	if err := row.Scan(&pb.ID, &pb.OperatorID, &pb.Version, &pb.Currency, &pb.Status, &pb.CreatedBy, &pb.CreatedAt, &pb.ActivatedAt); err != nil {
		if err == pgx.ErrNoRows {
			return PriceBook{}, false, nil
		}
		return PriceBook{}, false, fmt.Errorf("get price book: %w", err)
	}
	rules, err := getPriceRulesForBook(ctx, c, pb.ID)
	if err != nil {
		return PriceBook{}, false, err
	}
	pb.Rules = rules
	return pb, true, nil
}

func getPriceRulesForBook(ctx context.Context, c conn, priceBookID uuid.UUID) ([]PriceRule, error) {
	rows, err := c.Query(ctx, `SELECT id, price_book_id, usage_metric_key, unit_price FROM price_rules WHERE price_book_id = $1 ORDER BY usage_metric_key`, priceBookID)
	if err != nil {
		return nil, fmt.Errorf("list price rules: %w", err)
	}
	defer rows.Close()
	out := []PriceRule{}
	for rows.Next() {
		var r PriceRule
		if err := rows.Scan(&r.ID, &r.PriceBookID, &r.UsageMetricKey, &r.UnitPrice); err != nil {
			return nil, fmt.Errorf("scan price rule: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// activatePriceBook archives whatever was previously active for the same
// owner (operator_id, or the platform default when nil) and activates the
// target book -- create-new-then-supersede-old, the same discipline
// attestation_policies' revocation already established, never an in-place
// edit of a book that may already back real invoices.
func activatePriceBook(ctx context.Context, c conn, operatorID *uuid.UUID, id uuid.UUID) (bool, error) {
	if _, err := c.Exec(ctx, `UPDATE price_books SET status = 'archived' WHERE operator_id IS NOT DISTINCT FROM $1 AND status = 'active'`, operatorID); err != nil {
		return false, fmt.Errorf("archive previously active price book: %w", err)
	}
	tag, err := c.Exec(ctx, `
		UPDATE price_books SET status = 'active', activated_at = now()
		WHERE id = $1 AND operator_id IS NOT DISTINCT FROM $2 AND status = 'draft'
	`, id, operatorID)
	if err != nil {
		return false, fmt.Errorf("activate price book: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// resolveActivePriceBook returns the calling operator's own active price
// book, falling back to the platform default (operator_id IS NULL) if the
// operator has never activated one of its own.
func resolveActivePriceBook(ctx context.Context, c conn, operatorID uuid.UUID) (PriceBook, bool, error) {
	var pb PriceBook
	row := c.QueryRow(ctx, `
		SELECT id, operator_id, version, currency, status, created_by, created_at, activated_at
		FROM price_books WHERE operator_id = $1 AND status = 'active'
	`, operatorID)
	err := row.Scan(&pb.ID, &pb.OperatorID, &pb.Version, &pb.Currency, &pb.Status, &pb.CreatedBy, &pb.CreatedAt, &pb.ActivatedAt)
	if err != nil && err != pgx.ErrNoRows {
		return PriceBook{}, false, fmt.Errorf("resolve operator active price book: %w", err)
	}
	if err == nil {
		rules, rerr := getPriceRulesForBook(ctx, c, pb.ID)
		if rerr != nil {
			return PriceBook{}, false, rerr
		}
		pb.Rules = rules
		return pb, true, nil
	}

	row = c.QueryRow(ctx, `
		SELECT id, operator_id, version, currency, status, created_by, created_at, activated_at
		FROM price_books WHERE operator_id IS NULL AND status = 'active'
	`)
	if err := row.Scan(&pb.ID, &pb.OperatorID, &pb.Version, &pb.Currency, &pb.Status, &pb.CreatedBy, &pb.CreatedAt, &pb.ActivatedAt); err != nil {
		if err == pgx.ErrNoRows {
			return PriceBook{}, false, nil
		}
		return PriceBook{}, false, fmt.Errorf("resolve platform default price book: %w", err)
	}
	rules, err := getPriceRulesForBook(ctx, c, pb.ID)
	if err != nil {
		return PriceBook{}, false, err
	}
	pb.Rules = rules
	return pb, true, nil
}

func unitPriceFor(rules []PriceRule, metricKey string) (float64, bool) {
	for _, r := range rules {
		if r.UsageMetricKey == metricKey {
			return r.UnitPrice, true
		}
	}
	return 0, false
}

// ---------------------------------------------------------------------
// Quotes
// ---------------------------------------------------------------------

func createQuote(ctx context.Context, c conn, tenantID, operatorID, priceBookID uuid.UUID, lineItems []quoteLineItem, total float64, currency string, requestedBy uuid.UUID) (Quote, error) {
	lineItemsJSON, err := json.Marshal(lineItems)
	if err != nil {
		return Quote{}, fmt.Errorf("encode quote line items: %w", err)
	}
	var q Quote
	var lineItemsRaw []byte
	row := c.QueryRow(ctx, `
		INSERT INTO quotes (enterprise_tenant_id, operator_id, price_book_id, line_items, estimated_total, currency, requested_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, enterprise_tenant_id, operator_id, price_book_id, line_items, estimated_total, currency, requested_by, created_at
	`, tenantID, operatorID, priceBookID, lineItemsJSON, total, currency, requestedBy)
	if err := row.Scan(&q.ID, &q.EnterpriseTenantID, &q.OperatorID, &q.PriceBookID, &lineItemsRaw, &q.EstimatedTotal, &q.Currency, &q.RequestedBy, &q.CreatedAt); err != nil {
		return Quote{}, fmt.Errorf("insert quote: %w", err)
	}
	if err := json.Unmarshal(lineItemsRaw, &q.LineItems); err != nil {
		return Quote{}, fmt.Errorf("decode quote line items: %w", err)
	}
	return q, nil
}

func listQuotesForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]Quote, error) {
	rows, err := c.Query(ctx, `
		SELECT id, enterprise_tenant_id, operator_id, price_book_id, line_items, estimated_total, currency, requested_by, created_at
		FROM quotes WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC LIMIT 100
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list quotes: %w", err)
	}
	defer rows.Close()
	out := []Quote{}
	for rows.Next() {
		var q Quote
		var lineItemsRaw []byte
		if err := rows.Scan(&q.ID, &q.EnterpriseTenantID, &q.OperatorID, &q.PriceBookID, &lineItemsRaw, &q.EstimatedTotal, &q.Currency, &q.RequestedBy, &q.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan quote: %w", err)
		}
		if err := json.Unmarshal(lineItemsRaw, &q.LineItems); err != nil {
			return nil, fmt.Errorf("decode quote line items: %w", err)
		}
		out = append(out, q)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Budgets
// ---------------------------------------------------------------------

const budgetColumns = `id, enterprise_tenant_id, name, period_days, threshold_amount, currency, hard_limit, status, created_by, created_at, updated_at`

func scanBudget(row pgx.Row) (Budget, error) {
	var b Budget
	err := row.Scan(&b.ID, &b.EnterpriseTenantID, &b.Name, &b.PeriodDays, &b.ThresholdAmount, &b.Currency, &b.HardLimit, &b.Status, &b.CreatedBy, &b.CreatedAt, &b.UpdatedAt)
	return b, err
}

func createBudget(ctx context.Context, c conn, tenantID, createdBy uuid.UUID, in CreateBudgetInput) (Budget, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO budgets (enterprise_tenant_id, name, period_days, threshold_amount, currency, hard_limit, created_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING `+budgetColumns, tenantID, in.Name, in.PeriodDays, in.ThresholdAmount, in.Currency, in.HardLimit, createdBy)
	b, err := scanBudget(row)
	if err != nil {
		return Budget{}, fmt.Errorf("insert budget: %w", err)
	}
	return b, nil
}

func listBudgetsForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]Budget, error) {
	rows, err := c.Query(ctx, `SELECT `+budgetColumns+` FROM budgets WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list budgets: %w", err)
	}
	defer rows.Close()
	out := []Budget{}
	for rows.Next() {
		b, err := scanBudget(rows)
		if err != nil {
			return nil, fmt.Errorf("scan budget: %w", err)
		}
		out = append(out, b)
	}
	return out, rows.Err()
}

func getBudgetByIDTenant(ctx context.Context, c conn, tenantID, id uuid.UUID) (Budget, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+budgetColumns+` FROM budgets WHERE id = $1 AND enterprise_tenant_id = $2`, id, tenantID)
	b, err := scanBudget(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Budget{}, false, nil
		}
		return Budget{}, false, fmt.Errorf("get budget: %w", err)
	}
	return b, true, nil
}

func archiveBudget(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE budgets SET status = 'archived', updated_at = now() WHERE id = $1 AND status = 'active'`, id)
	if err != nil {
		return false, fmt.Errorf("archive budget: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// Invoices
// ---------------------------------------------------------------------

const invoiceColumns = `id, enterprise_tenant_id, operator_id, price_book_id, period_start, period_end, line_items,
	subtotal, tax_amount, total, currency, status, external_ref, issued_by, issued_at, updated_at`

func scanInvoice(row pgx.Row) (Invoice, error) {
	var inv Invoice
	var lineItemsRaw []byte
	err := row.Scan(&inv.ID, &inv.EnterpriseTenantID, &inv.OperatorID, &inv.PriceBookID, &inv.PeriodStart, &inv.PeriodEnd, &lineItemsRaw,
		&inv.Subtotal, &inv.TaxAmount, &inv.Total, &inv.Currency, &inv.Status, &inv.ExternalRef, &inv.IssuedBy, &inv.IssuedAt, &inv.UpdatedAt)
	if err != nil {
		return Invoice{}, err
	}
	if err := json.Unmarshal(lineItemsRaw, &inv.LineItems); err != nil {
		return Invoice{}, fmt.Errorf("decode invoice line items: %w", err)
	}
	return inv, nil
}

func createInvoice(ctx context.Context, c conn, tenantID, operatorID, priceBookID uuid.UUID, periodStart, periodEnd time.Time, lineItems []quoteLineItem, subtotal, taxAmount, total float64, currency string, issuedBy uuid.UUID) (Invoice, error) {
	lineItemsJSON, err := json.Marshal(lineItems)
	if err != nil {
		return Invoice{}, fmt.Errorf("encode invoice line items: %w", err)
	}
	row := c.QueryRow(ctx, `
		INSERT INTO invoices (enterprise_tenant_id, operator_id, price_book_id, period_start, period_end, line_items, subtotal, tax_amount, total, currency, issued_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		RETURNING `+invoiceColumns, tenantID, operatorID, priceBookID, periodStart, periodEnd, lineItemsJSON, subtotal, taxAmount, total, currency, issuedBy)
	inv, err := scanInvoice(row)
	if err != nil {
		return Invoice{}, fmt.Errorf("insert invoice: %w", err)
	}
	return inv, nil
}

func listInvoicesForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]Invoice, error) {
	rows, err := c.Query(ctx, `SELECT `+invoiceColumns+` FROM invoices WHERE enterprise_tenant_id = $1 ORDER BY issued_at DESC`, tenantID)
	return scanInvoices(rows, err)
}

func listInvoicesForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]Invoice, error) {
	rows, err := c.Query(ctx, `SELECT `+invoiceColumns+` FROM invoices WHERE operator_id = $1 ORDER BY issued_at DESC`, operatorID)
	return scanInvoices(rows, err)
}

func listInvoicesForOperatorAndTenant(ctx context.Context, c conn, operatorID, tenantID uuid.UUID) ([]Invoice, error) {
	rows, err := c.Query(ctx, `SELECT `+invoiceColumns+` FROM invoices WHERE operator_id = $1 AND enterprise_tenant_id = $2 ORDER BY issued_at DESC`, operatorID, tenantID)
	return scanInvoices(rows, err)
}

func scanInvoices(rows pgx.Rows, err error) ([]Invoice, error) {
	if err != nil {
		return nil, fmt.Errorf("list invoices: %w", err)
	}
	defer rows.Close()
	out := []Invoice{}
	for rows.Next() {
		inv, err := scanInvoice(rows)
		if err != nil {
			return nil, fmt.Errorf("scan invoice: %w", err)
		}
		out = append(out, inv)
	}
	return out, rows.Err()
}

func getInvoiceByIDTenant(ctx context.Context, c conn, tenantID, id uuid.UUID) (Invoice, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+invoiceColumns+` FROM invoices WHERE id = $1 AND enterprise_tenant_id = $2`, id, tenantID)
	inv, err := scanInvoice(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Invoice{}, false, nil
		}
		return Invoice{}, false, fmt.Errorf("get invoice: %w", err)
	}
	return inv, true, nil
}

func getInvoiceByIDOperator(ctx context.Context, c conn, operatorID, id uuid.UUID) (Invoice, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+invoiceColumns+` FROM invoices WHERE id = $1 AND operator_id = $2`, id, operatorID)
	inv, err := scanInvoice(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Invoice{}, false, nil
		}
		return Invoice{}, false, fmt.Errorf("get invoice: %w", err)
	}
	return inv, true, nil
}

func setInvoiceStatus(ctx context.Context, c conn, id uuid.UUID, status string) error {
	_, err := c.Exec(ctx, `UPDATE invoices SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("set invoice status: %w", err)
	}
	return nil
}

func setInvoiceExternalRef(ctx context.Context, c conn, id uuid.UUID, ref string) error {
	_, err := c.Exec(ctx, `UPDATE invoices SET external_ref = $2, updated_at = now() WHERE id = $1`, id, ref)
	if err != nil {
		return fmt.Errorf("set invoice external ref: %w", err)
	}
	return nil
}

// ---------------------------------------------------------------------
// Settlement records
// ---------------------------------------------------------------------

const settlementColumns = `id, operator_id, enterprise_tenant_id, bilateral_agreement_id, period_start, period_end,
	gross_amount, platform_fee_amount, net_amount, currency, status, invoice_count, created_by, created_at, reconciled_at`

func scanSettlement(row pgx.Row) (SettlementRecord, error) {
	var s SettlementRecord
	err := row.Scan(&s.ID, &s.OperatorID, &s.EnterpriseTenantID, &s.BilateralAgreementID, &s.PeriodStart, &s.PeriodEnd,
		&s.GrossAmount, &s.PlatformFeeAmount, &s.NetAmount, &s.Currency, &s.Status, &s.InvoiceCount, &s.CreatedBy, &s.CreatedAt, &s.ReconciledAt)
	return s, err
}

func createSettlement(ctx context.Context, c conn, operatorID uuid.UUID, tenantID, agreementID *uuid.UUID, periodStart, periodEnd time.Time, gross, platformFee, net float64, currency string, invoiceCount int, createdBy uuid.UUID) (SettlementRecord, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO settlement_records (operator_id, enterprise_tenant_id, bilateral_agreement_id, period_start, period_end, gross_amount, platform_fee_amount, net_amount, currency, invoice_count, created_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		RETURNING `+settlementColumns, operatorID, tenantID, agreementID, periodStart, periodEnd, gross, platformFee, net, currency, invoiceCount, createdBy)
	s, err := scanSettlement(row)
	if err != nil {
		return SettlementRecord{}, fmt.Errorf("insert settlement record: %w", err)
	}
	return s, nil
}

func listSettlementsForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]SettlementRecord, error) {
	rows, err := c.Query(ctx, `SELECT `+settlementColumns+` FROM settlement_records WHERE operator_id = $1 ORDER BY period_start DESC`, operatorID)
	if err != nil {
		return nil, fmt.Errorf("list settlement records: %w", err)
	}
	defer rows.Close()
	out := []SettlementRecord{}
	for rows.Next() {
		s, err := scanSettlement(rows)
		if err != nil {
			return nil, fmt.Errorf("scan settlement record: %w", err)
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

func getSettlementByIDOperator(ctx context.Context, c conn, operatorID, id uuid.UUID) (SettlementRecord, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+settlementColumns+` FROM settlement_records WHERE id = $1 AND operator_id = $2`, id, operatorID)
	s, err := scanSettlement(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return SettlementRecord{}, false, nil
		}
		return SettlementRecord{}, false, fmt.Errorf("get settlement record: %w", err)
	}
	return s, true, nil
}

func reconcileSettlement(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `UPDATE settlement_records SET status = 'reconciled', reconciled_at = now() WHERE id = $1 AND status = 'pending'`, id)
	if err != nil {
		return false, fmt.Errorf("reconcile settlement record: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// Adjustments (append-only)
// ---------------------------------------------------------------------

func insertAdjustment(ctx context.Context, c conn, invoiceID, settlementID *uuid.UUID, operatorID uuid.UUID, tenantID *uuid.UUID, amount float64, reason string, createdBy uuid.UUID) (Adjustment, error) {
	var a Adjustment
	row := c.QueryRow(ctx, `
		INSERT INTO adjustments (invoice_id, settlement_id, operator_id, enterprise_tenant_id, amount, reason, created_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, invoice_id, settlement_id, operator_id, enterprise_tenant_id, amount, reason, created_by, created_at
	`, invoiceID, settlementID, operatorID, tenantID, amount, reason, createdBy)
	if err := row.Scan(&a.ID, &a.InvoiceID, &a.SettlementID, &a.OperatorID, &a.EnterpriseTenantID, &a.Amount, &a.Reason, &a.CreatedBy, &a.CreatedAt); err != nil {
		return Adjustment{}, fmt.Errorf("insert adjustment: %w", err)
	}
	return a, nil
}

func listAdjustmentsForInvoice(ctx context.Context, c conn, invoiceID uuid.UUID) ([]Adjustment, error) {
	rows, err := c.Query(ctx, `
		SELECT id, invoice_id, settlement_id, operator_id, enterprise_tenant_id, amount, reason, created_by, created_at
		FROM adjustments WHERE invoice_id = $1 ORDER BY created_at
	`, invoiceID)
	return scanAdjustments(rows, err)
}

func listAdjustmentsForSettlement(ctx context.Context, c conn, settlementID uuid.UUID) ([]Adjustment, error) {
	rows, err := c.Query(ctx, `
		SELECT id, invoice_id, settlement_id, operator_id, enterprise_tenant_id, amount, reason, created_by, created_at
		FROM adjustments WHERE settlement_id = $1 ORDER BY created_at
	`, settlementID)
	return scanAdjustments(rows, err)
}

func scanAdjustments(rows pgx.Rows, err error) ([]Adjustment, error) {
	if err != nil {
		return nil, fmt.Errorf("list adjustments: %w", err)
	}
	defer rows.Close()
	out := []Adjustment{}
	for rows.Next() {
		var a Adjustment
		if err := rows.Scan(&a.ID, &a.InvoiceID, &a.SettlementID, &a.OperatorID, &a.EnterpriseTenantID, &a.Amount, &a.Reason, &a.CreatedBy, &a.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan adjustment: %w", err)
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Credit notes
// ---------------------------------------------------------------------

func insertCreditNote(ctx context.Context, c conn, invoiceID, tenantID, operatorID uuid.UUID, amount float64, reason string, createdBy uuid.UUID) (CreditNote, error) {
	var cn CreditNote
	row := c.QueryRow(ctx, `
		INSERT INTO credit_notes (invoice_id, enterprise_tenant_id, operator_id, amount, reason, created_by)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, invoice_id, enterprise_tenant_id, operator_id, amount, reason, status, created_by, created_at, applied_at
	`, invoiceID, tenantID, operatorID, amount, reason, createdBy)
	if err := row.Scan(&cn.ID, &cn.InvoiceID, &cn.EnterpriseTenantID, &cn.OperatorID, &cn.Amount, &cn.Reason, &cn.Status, &cn.CreatedBy, &cn.CreatedAt, &cn.AppliedAt); err != nil {
		return CreditNote{}, fmt.Errorf("insert credit note: %w", err)
	}
	return cn, nil
}

func listCreditNotesForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]CreditNote, error) {
	rows, err := c.Query(ctx, `
		SELECT id, invoice_id, enterprise_tenant_id, operator_id, amount, reason, status, created_by, created_at, applied_at
		FROM credit_notes WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC
	`, tenantID)
	return scanCreditNotes(rows, err)
}

func listCreditNotesForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]CreditNote, error) {
	rows, err := c.Query(ctx, `
		SELECT id, invoice_id, enterprise_tenant_id, operator_id, amount, reason, status, created_by, created_at, applied_at
		FROM credit_notes WHERE operator_id = $1 ORDER BY created_at DESC
	`, operatorID)
	return scanCreditNotes(rows, err)
}

func scanCreditNotes(rows pgx.Rows, err error) ([]CreditNote, error) {
	if err != nil {
		return nil, fmt.Errorf("list credit notes: %w", err)
	}
	defer rows.Close()
	out := []CreditNote{}
	for rows.Next() {
		var cn CreditNote
		if err := rows.Scan(&cn.ID, &cn.InvoiceID, &cn.EnterpriseTenantID, &cn.OperatorID, &cn.Amount, &cn.Reason, &cn.Status, &cn.CreatedBy, &cn.CreatedAt, &cn.AppliedAt); err != nil {
			return nil, fmt.Errorf("scan credit note: %w", err)
		}
		out = append(out, cn)
	}
	return out, rows.Err()
}

// ---------------------------------------------------------------------
// Billing disputes
// ---------------------------------------------------------------------

const disputeColumns = `id, invoice_id, enterprise_tenant_id, operator_id, reason, status, resolution_note, opened_by, resolved_by, opened_at, resolved_at`

func scanDispute(row pgx.Row) (BillingDispute, error) {
	var d BillingDispute
	err := row.Scan(&d.ID, &d.InvoiceID, &d.EnterpriseTenantID, &d.OperatorID, &d.Reason, &d.Status, &d.ResolutionNote, &d.OpenedBy, &d.ResolvedBy, &d.OpenedAt, &d.ResolvedAt)
	return d, err
}

func createDispute(ctx context.Context, c conn, invoiceID, tenantID, operatorID uuid.UUID, reason string, openedBy uuid.UUID) (BillingDispute, error) {
	row := c.QueryRow(ctx, `
		INSERT INTO billing_disputes (invoice_id, enterprise_tenant_id, operator_id, reason, opened_by)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING `+disputeColumns, invoiceID, tenantID, operatorID, reason, openedBy)
	d, err := scanDispute(row)
	if err != nil {
		return BillingDispute{}, fmt.Errorf("insert billing dispute: %w", err)
	}
	return d, nil
}

func listDisputesForTenant(ctx context.Context, c conn, tenantID uuid.UUID) ([]BillingDispute, error) {
	rows, err := c.Query(ctx, `SELECT `+disputeColumns+` FROM billing_disputes WHERE enterprise_tenant_id = $1 ORDER BY opened_at DESC`, tenantID)
	return scanDisputes(rows, err)
}

func listDisputesForOperator(ctx context.Context, c conn, operatorID uuid.UUID) ([]BillingDispute, error) {
	rows, err := c.Query(ctx, `SELECT `+disputeColumns+` FROM billing_disputes WHERE operator_id = $1 ORDER BY opened_at DESC`, operatorID)
	return scanDisputes(rows, err)
}

func scanDisputes(rows pgx.Rows, err error) ([]BillingDispute, error) {
	if err != nil {
		return nil, fmt.Errorf("list billing disputes: %w", err)
	}
	defer rows.Close()
	out := []BillingDispute{}
	for rows.Next() {
		d, err := scanDispute(rows)
		if err != nil {
			return nil, fmt.Errorf("scan billing dispute: %w", err)
		}
		out = append(out, d)
	}
	return out, rows.Err()
}

func getDisputeByIDOperator(ctx context.Context, c conn, operatorID, id uuid.UUID) (BillingDispute, bool, error) {
	row := c.QueryRow(ctx, `SELECT `+disputeColumns+` FROM billing_disputes WHERE id = $1 AND operator_id = $2`, id, operatorID)
	d, err := scanDispute(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return BillingDispute{}, false, nil
		}
		return BillingDispute{}, false, fmt.Errorf("get billing dispute: %w", err)
	}
	return d, true, nil
}

func resolveDispute(ctx context.Context, c conn, id, resolvedBy uuid.UUID, status, note string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE billing_disputes SET status = $2, resolution_note = $3, resolved_by = $4, resolved_at = now()
		WHERE id = $1 AND status IN ('open', 'under_review')
	`, id, status, note, resolvedBy)
	if err != nil {
		return false, fmt.Errorf("resolve billing dispute: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

// ---------------------------------------------------------------------
// Billing provider events (append-only)
// ---------------------------------------------------------------------

func insertBillingProviderEvent(ctx context.Context, c conn, invoiceID, settlementID *uuid.UUID, operatorID uuid.UUID, tenantID *uuid.UUID, providerType, eventType string, externalRef *string, detail map[string]any) (BillingProviderEvent, error) {
	detailJSON, err := json.Marshal(detail)
	if err != nil {
		return BillingProviderEvent{}, fmt.Errorf("encode billing provider event detail: %w", err)
	}
	var e BillingProviderEvent
	var detailRaw []byte
	row := c.QueryRow(ctx, `
		INSERT INTO billing_provider_events (invoice_id, settlement_id, operator_id, enterprise_tenant_id, provider_type, event_type, external_ref, detail)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING id, invoice_id, settlement_id, provider_type, event_type, external_ref, detail, occurred_at
	`, invoiceID, settlementID, operatorID, tenantID, providerType, eventType, externalRef, detailJSON)
	if err := row.Scan(&e.ID, &e.InvoiceID, &e.SettlementID, &e.ProviderType, &e.EventType, &e.ExternalRef, &detailRaw, &e.OccurredAt); err != nil {
		return BillingProviderEvent{}, fmt.Errorf("insert billing provider event: %w", err)
	}
	if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
		return BillingProviderEvent{}, fmt.Errorf("decode billing provider event detail: %w", err)
	}
	return e, nil
}

func listBillingProviderEventsForInvoice(ctx context.Context, c conn, invoiceID uuid.UUID) ([]BillingProviderEvent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, invoice_id, settlement_id, provider_type, event_type, external_ref, detail, occurred_at
		FROM billing_provider_events WHERE invoice_id = $1 ORDER BY occurred_at
	`, invoiceID)
	return scanBillingProviderEvents(rows, err)
}

func listBillingProviderEventsForSettlement(ctx context.Context, c conn, settlementID uuid.UUID) ([]BillingProviderEvent, error) {
	rows, err := c.Query(ctx, `
		SELECT id, invoice_id, settlement_id, provider_type, event_type, external_ref, detail, occurred_at
		FROM billing_provider_events WHERE settlement_id = $1 ORDER BY occurred_at
	`, settlementID)
	return scanBillingProviderEvents(rows, err)
}

func scanBillingProviderEvents(rows pgx.Rows, err error) ([]BillingProviderEvent, error) {
	if err != nil {
		return nil, fmt.Errorf("list billing provider events: %w", err)
	}
	defer rows.Close()
	out := []BillingProviderEvent{}
	for rows.Next() {
		var e BillingProviderEvent
		var detailRaw []byte
		if err := rows.Scan(&e.ID, &e.InvoiceID, &e.SettlementID, &e.ProviderType, &e.EventType, &e.ExternalRef, &detailRaw, &e.OccurredAt); err != nil {
			return nil, fmt.Errorf("scan billing provider event: %w", err)
		}
		if err := json.Unmarshal(detailRaw, &e.Detail); err != nil {
			return nil, fmt.Errorf("decode billing provider event detail: %w", err)
		}
		out = append(out, e)
	}
	return out, rows.Err()
}
