// Package subscriptions resolves entitlements from a tenant/operator's
// active subscription plan and its plan_features. Entitlements are always
// re-derivable from Postgres (the system of record); Redis only serves as a
// short-TTL read-through cache so entitlement checks stay cheap on the hot
// path -- a cache miss or Redis outage falls back to Postgres, never to an
// "allow by default" decision.
package subscriptions

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	"gridkeep/control-api/internal/platform/cache"
	dbpkg "gridkeep/control-api/internal/platform/db"
)

const cacheTTL = 60 * time.Second

type Service struct {
	store *dbpkg.Store
	cache *cache.Client
}

func NewService(store *dbpkg.Store, c *cache.Client) *Service {
	return &Service{store: store, cache: c}
}

func (s *Service) GetEnterpriseEntitlements(ctx context.Context) (Entitlements, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	tenantID := *scope.TenantID

	cacheKey := fmt.Sprintf("entitlements:enterprise:%s", tenantID)
	if s.cache != nil {
		if raw, err := s.cache.Raw().Get(ctx, cacheKey).Result(); err == nil {
			var ent Entitlements
			if json.Unmarshal([]byte(raw), &ent) == nil {
				return ent, nil
			}
		}
	}

	sub, ok, err := getActiveEnterpriseSubscription(ctx, scopedTx.Tx, tenantID)
	if err != nil {
		return Entitlements{}, err
	}
	if !ok {
		return Entitlements{Status: "none", Features: map[string]any{}}, nil
	}
	features, err := getPlanFeatures(ctx, scopedTx.Tx, sub.PlanID)
	if err != nil {
		return Entitlements{}, err
	}
	ent := Entitlements{PlanKey: sub.PlanKey, PlanName: sub.PlanName, Status: sub.Status, Features: features}

	if s.cache != nil {
		if raw, err := json.Marshal(ent); err == nil {
			_ = s.cache.Raw().Set(ctx, cacheKey, raw, cacheTTL).Err()
		}
	}
	return ent, nil
}

func (s *Service) GetOperatorEntitlements(ctx context.Context) (Entitlements, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	operatorID := *scope.OperatorID

	cacheKey := fmt.Sprintf("entitlements:operator:%s", operatorID)
	if s.cache != nil {
		if raw, err := s.cache.Raw().Get(ctx, cacheKey).Result(); err == nil {
			var ent Entitlements
			if json.Unmarshal([]byte(raw), &ent) == nil {
				return ent, nil
			}
		}
	}

	sub, ok, err := getActiveOperatorSubscription(ctx, scopedTx.Tx, operatorID)
	if err != nil {
		return Entitlements{}, err
	}
	if !ok {
		return Entitlements{Status: "none", Features: map[string]any{}}, nil
	}
	features, err := getPlanFeatures(ctx, scopedTx.Tx, sub.PlanID)
	if err != nil {
		return Entitlements{}, err
	}
	ent := Entitlements{PlanKey: sub.PlanKey, PlanName: sub.PlanName, Status: sub.Status, Features: features}

	if s.cache != nil {
		if raw, err := json.Marshal(ent); err == nil {
			_ = s.cache.Raw().Set(ctx, cacheKey, raw, cacheTTL).Err()
		}
	}
	return ent, nil
}

// AssignEnterprisePlan is a platform-administration action: it runs inside
// the platform-scoped transaction the platformadmin module's rbac
// middleware already opened.
func (s *Service) AssignEnterprisePlan(ctx context.Context, actorUserID, tenantID uuid.UUID, planKey string) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	planID, err := getPlanByKey(ctx, scopedTx.Tx, planKey)
	if err != nil {
		return err
	}
	if err := upsertEnterpriseSubscription(ctx, scopedTx.Tx, tenantID, planID); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actorUserID,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     &tenantID,
		Action:      "subscriptions.enterprise_plan_assigned",
		TargetType:  "enterprise_tenant",
		TargetID:    &tenantID,
		Evidence:    map[string]any{"plan_key": planKey},
	}); err != nil {
		return err
	}
	if s.cache != nil {
		_ = s.cache.Raw().Del(ctx, fmt.Sprintf("entitlements:enterprise:%s", tenantID)).Err()
	}
	return scopedTx.Commit(ctx)
}

func (s *Service) AssignOperatorPlan(ctx context.Context, actorUserID, operatorID uuid.UUID, planKey string) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	planID, err := getPlanByKey(ctx, scopedTx.Tx, planKey)
	if err != nil {
		return err
	}
	if err := upsertOperatorSubscription(ctx, scopedTx.Tx, operatorID, planID); err != nil {
		return err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actorUserID,
		ScopeType:   audit.ScopeOperator,
		ScopeID:     &operatorID,
		Action:      "subscriptions.operator_plan_assigned",
		TargetType:  "operator",
		TargetID:    &operatorID,
		Evidence:    map[string]any{"plan_key": planKey},
	}); err != nil {
		return err
	}
	if s.cache != nil {
		_ = s.cache.Raw().Del(ctx, fmt.Sprintf("entitlements:operator:%s", operatorID)).Err()
	}
	return scopedTx.Commit(ctx)
}
