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

// TestMockWorkloadLifecycle proves the deploy/scale/pause/resume/rollback/
// terminate ordering discipline: every workload-scoped operation requires
// the workload to already be deployed (except Deploy itself, which
// requires the namespace to exist), and Resume requires the workload to
// actually be paused first.
func TestMockWorkloadLifecycle(t *testing.T) {
	ctx := context.Background()
	m := NewMock()

	if err := m.DeployWorkload(ctx, "does-not-exist", "dep-1", map[string]any{}, 2); err == nil {
		t.Fatalf("expected an error deploying into a namespace that was never created")
	}

	if err := m.CreateNamespace(ctx, "tenant-a"); err != nil {
		t.Fatalf("create namespace: %v", err)
	}
	if err := m.ScaleWorkload(ctx, "dep-1", 3); err == nil {
		t.Fatalf("expected an error scaling a deployment that was never deployed")
	}

	if err := m.DeployWorkload(ctx, "tenant-a", "dep-1", map[string]any{"image": "fictional:v1"}, 2); err != nil {
		t.Fatalf("deploy workload: %v", err)
	}
	state, ok := m.GetWorkloadState("dep-1")
	if !ok || state.ReplicaCount != 2 || state.Status != "running" {
		t.Fatalf("expected a running deployment with 2 replicas, got %+v (exists=%v)", state, ok)
	}

	if err := m.ScaleWorkload(ctx, "dep-1", 5); err != nil {
		t.Fatalf("scale workload: %v", err)
	}
	if state, _ := m.GetWorkloadState("dep-1"); state.ReplicaCount != 5 {
		t.Fatalf("expected 5 replicas after scaling, got %d", state.ReplicaCount)
	}

	if err := m.ResumeWorkload(ctx, "dep-1"); err == nil {
		t.Fatalf("expected an error resuming a deployment that was never paused")
	}
	if err := m.PauseWorkload(ctx, "dep-1"); err != nil {
		t.Fatalf("pause workload: %v", err)
	}
	if state, _ := m.GetWorkloadState("dep-1"); state.Status != "paused" {
		t.Fatalf("expected status paused, got %q", state.Status)
	}
	if err := m.ResumeWorkload(ctx, "dep-1"); err != nil {
		t.Fatalf("resume workload: %v", err)
	}
	if state, _ := m.GetWorkloadState("dep-1"); state.Status != "running" {
		t.Fatalf("expected status running after resume, got %q", state.Status)
	}

	if err := m.RollbackWorkload(ctx, "dep-1", map[string]any{"image": "fictional:v0"}); err != nil {
		t.Fatalf("rollback workload: %v", err)
	}
	if state, _ := m.GetWorkloadState("dep-1"); state.Manifest["image"] != "fictional:v0" {
		t.Fatalf("expected rolled-back manifest, got %v", state.Manifest)
	}

	if err := m.TerminateWorkload(ctx, "dep-1"); err != nil {
		t.Fatalf("terminate workload: %v", err)
	}
	if state, _ := m.GetWorkloadState("dep-1"); state.Status != "terminated" {
		t.Fatalf("expected status terminated, got %q", state.Status)
	}

	if err := m.TerminateWorkload(ctx, "never-deployed"); err == nil {
		t.Fatalf("expected an error terminating a deployment that was never deployed")
	}
}
