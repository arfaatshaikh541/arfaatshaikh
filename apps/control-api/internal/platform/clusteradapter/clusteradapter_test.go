package clusteradapter

import (
	"context"
	"testing"
)

// TestMockRequiresNamespaceBeforeApplyingScopedResources proves the
// interface's own ordering discipline: a quota/policy/security-context can
// never be applied to a namespace that was not first created through this
// same narrow interface -- there is no "apply to any namespace" shortcut.
func TestMockRequiresNamespaceBeforeApplyingScopedResources(t *testing.T) {
	ctx := context.Background()
	m := NewMock()

	if err := m.ApplyResourceQuota(ctx, "does-not-exist", map[string]any{"cpu": "4"}); err == nil {
		t.Fatalf("expected an error applying a quota to a namespace that was never created")
	}

	if err := m.CreateNamespace(ctx, "tenant-workload"); err != nil {
		t.Fatalf("create namespace: %v", err)
	}
	if err := m.ApplyResourceQuota(ctx, "tenant-workload", map[string]any{"cpu": "4"}); err != nil {
		t.Fatalf("apply resource quota: %v", err)
	}
	if err := m.ApplyNetworkPolicy(ctx, "tenant-workload", map[string]any{"deny_by_default": true}); err != nil {
		t.Fatalf("apply network policy: %v", err)
	}
	if err := m.ApplySecurityContext(ctx, "tenant-workload", map[string]any{"run_as_non_root": true}); err != nil {
		t.Fatalf("apply security context: %v", err)
	}

	quota, policy, sc, exists := m.NamespaceState("tenant-workload")
	if !exists {
		t.Fatalf("expected namespace to exist")
	}
	if quota["cpu"] != "4" {
		t.Fatalf("expected quota to be recorded, got %v", quota)
	}
	if policy["deny_by_default"] != true {
		t.Fatalf("expected network policy to be recorded, got %v", policy)
	}
	if sc["run_as_non_root"] != true {
		t.Fatalf("expected security context to be recorded, got %v", sc)
	}

	health, err := m.Health(ctx)
	if err != nil || !health.Healthy {
		t.Fatalf("expected healthy status, got %+v, err=%v", health, err)
	}
}
