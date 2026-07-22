package subscriptions

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

type activeSubscription struct {
	PlanID   uuid.UUID
	PlanKey  string
	PlanName string
	Status   string
}

func getActiveEnterpriseSubscription(ctx context.Context, c conn, tenantID uuid.UUID) (activeSubscription, bool, error) {
	var s activeSubscription
	err := c.QueryRow(ctx, `
		SELECT p.id, p.key, p.name, es.status
		FROM enterprise_subscriptions es
		JOIN subscription_plans p ON p.id = es.plan_id
		WHERE es.enterprise_tenant_id = $1 AND es.status = 'active'
		ORDER BY es.started_at DESC LIMIT 1
	`, tenantID).Scan(&s.PlanID, &s.PlanKey, &s.PlanName, &s.Status)
	if err != nil {
		if err == pgx.ErrNoRows {
			return activeSubscription{}, false, nil
		}
		return activeSubscription{}, false, fmt.Errorf("get active enterprise subscription: %w", err)
	}
	return s, true, nil
}

func getActiveOperatorSubscription(ctx context.Context, c conn, operatorID uuid.UUID) (activeSubscription, bool, error) {
	var s activeSubscription
	err := c.QueryRow(ctx, `
		SELECT p.id, p.key, p.name, os.status
		FROM operator_subscriptions os
		JOIN subscription_plans p ON p.id = os.plan_id
		WHERE os.operator_id = $1 AND os.status = 'active'
		ORDER BY os.started_at DESC LIMIT 1
	`, operatorID).Scan(&s.PlanID, &s.PlanKey, &s.PlanName, &s.Status)
	if err != nil {
		if err == pgx.ErrNoRows {
			return activeSubscription{}, false, nil
		}
		return activeSubscription{}, false, fmt.Errorf("get active operator subscription: %w", err)
	}
	return s, true, nil
}

func getPlanFeatures(ctx context.Context, c conn, planID uuid.UUID) (map[string]any, error) {
	rows, err := c.Query(ctx, `
		SELECT f.key, pf.limit_value
		FROM plan_features pf
		JOIN features f ON f.id = pf.feature_id
		WHERE pf.plan_id = $1
	`, planID)
	if err != nil {
		return nil, fmt.Errorf("get plan features: %w", err)
	}
	defer rows.Close()

	out := map[string]any{}
	for rows.Next() {
		var key string
		var raw []byte
		if err := rows.Scan(&key, &raw); err != nil {
			return nil, fmt.Errorf("scan plan feature: %w", err)
		}
		var val any
		if len(raw) > 0 {
			if err := json.Unmarshal(raw, &val); err != nil {
				return nil, fmt.Errorf("unmarshal plan feature limit: %w", err)
			}
		}
		out[key] = val
	}
	return out, rows.Err()
}

func getPlanByKey(ctx context.Context, c conn, key string) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `SELECT id FROM subscription_plans WHERE key = $1`, key).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("get plan by key %s: %w", key, err)
	}
	return id, nil
}

func upsertEnterpriseSubscription(ctx context.Context, c conn, tenantID, planID uuid.UUID) error {
	_, err := c.Exec(ctx, `
		UPDATE enterprise_subscriptions SET status = 'cancelled' WHERE enterprise_tenant_id = $1 AND status = 'active'
	`, tenantID)
	if err != nil {
		return fmt.Errorf("cancel prior enterprise subscription: %w", err)
	}
	_, err = c.Exec(ctx, `
		INSERT INTO enterprise_subscriptions (enterprise_tenant_id, plan_id) VALUES ($1, $2)
	`, tenantID, planID)
	if err != nil {
		return fmt.Errorf("insert enterprise subscription: %w", err)
	}
	return nil
}

func upsertOperatorSubscription(ctx context.Context, c conn, operatorID, planID uuid.UUID) error {
	_, err := c.Exec(ctx, `
		UPDATE operator_subscriptions SET status = 'cancelled' WHERE operator_id = $1 AND status = 'active'
	`, operatorID)
	if err != nil {
		return fmt.Errorf("cancel prior operator subscription: %w", err)
	}
	_, err = c.Exec(ctx, `
		INSERT INTO operator_subscriptions (operator_id, plan_id) VALUES ($1, $2)
	`, operatorID, planID)
	if err != nil {
		return fmt.Errorf("insert operator subscription: %w", err)
	}
	return nil
}
