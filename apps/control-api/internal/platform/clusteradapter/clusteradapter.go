// Package clusteradapter defines the narrow, named set of operations a
// cluster agent may perform against the Kubernetes cluster it runs
// alongside -- namespace creation, resource quotas, network policies,
// security contexts, and (Milestone 7) deploying, scaling, pausing,
// resuming, rolling back, and terminating a workload. This interface *is*
// the delegated-access boundary the approved architecture requires ("do
// not give the central control plane unrestricted cluster-admin access";
// "use delegated, policy-restricted access"): there is no method here for
// arbitrary manifest application, no method that takes a raw Kubernetes
// API request, and control-api itself never holds a kubeconfig or calls
// any of this directly -- only a cluster agent (Milestone 6/7's
// cmd/mockclusteragent today; a real daemon running inside the operator's
// cluster in production) does, and only through this exact, reviewable
// method set. Every workload-scoped method (deploy/scale/pause/resume/
// rollback/terminate) is keyed by deploymentID, never by a raw manifest or
// resource name a caller could point at something else.
//
// The only implementation in this codebase is the in-memory Mock below.
// This milestone does not integrate a real Kubernetes client (client-go)
// -- there is no live cluster in this environment to integrate against,
// and doing so would not be exercised by anything. A real implementation
// wrapping client-go, scoped to a ServiceAccount with exactly the RBAC
// permissions this interface's methods need and no more, is future work
// for whichever milestone stands up a real cluster-agent daemon.
package clusteradapter

import (
	"context"
	"fmt"
	"sync"
)

type Health struct {
	Healthy bool   `json:"healthy"`
	Detail  string `json:"detail"`
}

// WorkloadState is a read-only snapshot of what the mock adapter believes
// is currently deployed -- used by cmd/mockclusteragent and tests to
// report/assert on adapter-side state without exposing the adapter's
// internal maps directly.
type WorkloadState struct {
	Namespace    string
	Manifest     map[string]any
	ReplicaCount int
	Status       string // "running", "paused", "terminated"
}

type ClusterAdapter interface {
	CreateNamespace(ctx context.Context, name string) error
	ApplyResourceQuota(ctx context.Context, namespace string, quota map[string]any) error
	ApplyNetworkPolicy(ctx context.Context, namespace string, policy map[string]any) error
	ApplySecurityContext(ctx context.Context, namespace string, securityContext map[string]any) error
	Health(ctx context.Context) (Health, error)

	DeployWorkload(ctx context.Context, namespace, deploymentID string, manifest map[string]any, replicaCount int) error
	ScaleWorkload(ctx context.Context, deploymentID string, replicaCount int) error
	PauseWorkload(ctx context.Context, deploymentID string) error
	ResumeWorkload(ctx context.Context, deploymentID string) error
	RollbackWorkload(ctx context.Context, deploymentID string, manifest map[string]any) error
	TerminateWorkload(ctx context.Context, deploymentID string) error
}

// Mock is an in-memory ClusterAdapter -- it proves the protocol (a
// namespace must exist before a quota/policy/security-context can be
// applied to it, a workload must be deployed before it can be scaled/
// paused/resumed/rolled-back/terminated, every operation is scoped to a
// namespace or deployment ID, never cluster-wide) without touching a real
// Kubernetes API. Safe for concurrent use.
type Mock struct {
	mu               sync.Mutex
	namespaces       map[string]bool
	resourceQuotas   map[string]map[string]any
	networkPolicies  map[string]map[string]any
	securityContexts map[string]map[string]any
	workloads        map[string]*WorkloadState
}

func NewMock() *Mock {
	return &Mock{
		namespaces:       make(map[string]bool),
		resourceQuotas:   make(map[string]map[string]any),
		networkPolicies:  make(map[string]map[string]any),
		securityContexts: make(map[string]map[string]any),
		workloads:        make(map[string]*WorkloadState),
	}
}

func (m *Mock) CreateNamespace(_ context.Context, name string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.namespaces[name] = true
	return nil
}

func (m *Mock) ApplyResourceQuota(_ context.Context, namespace string, quota map[string]any) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if !m.namespaces[namespace] {
		return fmt.Errorf("namespace %q does not exist", namespace)
	}
	m.resourceQuotas[namespace] = quota
	return nil
}

func (m *Mock) ApplyNetworkPolicy(_ context.Context, namespace string, policy map[string]any) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if !m.namespaces[namespace] {
		return fmt.Errorf("namespace %q does not exist", namespace)
	}
	m.networkPolicies[namespace] = policy
	return nil
}

func (m *Mock) ApplySecurityContext(_ context.Context, namespace string, securityContext map[string]any) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if !m.namespaces[namespace] {
		return fmt.Errorf("namespace %q does not exist", namespace)
	}
	m.securityContexts[namespace] = securityContext
	return nil
}

func (m *Mock) Health(_ context.Context) (Health, error) {
	return Health{Healthy: true, Detail: "mock cluster adapter"}, nil
}

// NamespaceState is a read-only snapshot used by tests and the mock
// cluster agent CLI to report what it locally applied, without exposing
// the adapter's internal maps directly.
func (m *Mock) NamespaceState(namespace string) (quota, networkPolicy, securityContext map[string]any, exists bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if !m.namespaces[namespace] {
		return nil, nil, nil, false
	}
	return m.resourceQuotas[namespace], m.networkPolicies[namespace], m.securityContexts[namespace], true
}

func (m *Mock) DeployWorkload(_ context.Context, namespace, deploymentID string, manifest map[string]any, replicaCount int) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if !m.namespaces[namespace] {
		return fmt.Errorf("namespace %q does not exist", namespace)
	}
	if replicaCount <= 0 {
		return fmt.Errorf("replica count must be positive, got %d", replicaCount)
	}
	m.workloads[deploymentID] = &WorkloadState{
		Namespace: namespace, Manifest: manifest, ReplicaCount: replicaCount, Status: "running",
	}
	return nil
}

func (m *Mock) ScaleWorkload(_ context.Context, deploymentID string, replicaCount int) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	w, ok := m.workloads[deploymentID]
	if !ok {
		return fmt.Errorf("deployment %q is not deployed", deploymentID)
	}
	if replicaCount <= 0 {
		return fmt.Errorf("replica count must be positive, got %d", replicaCount)
	}
	w.ReplicaCount = replicaCount
	return nil
}

func (m *Mock) PauseWorkload(_ context.Context, deploymentID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	w, ok := m.workloads[deploymentID]
	if !ok {
		return fmt.Errorf("deployment %q is not deployed", deploymentID)
	}
	w.Status = "paused"
	return nil
}

func (m *Mock) ResumeWorkload(_ context.Context, deploymentID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	w, ok := m.workloads[deploymentID]
	if !ok {
		return fmt.Errorf("deployment %q is not deployed", deploymentID)
	}
	if w.Status != "paused" {
		return fmt.Errorf("deployment %q is not paused", deploymentID)
	}
	w.Status = "running"
	return nil
}

func (m *Mock) RollbackWorkload(_ context.Context, deploymentID string, manifest map[string]any) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	w, ok := m.workloads[deploymentID]
	if !ok {
		return fmt.Errorf("deployment %q is not deployed", deploymentID)
	}
	w.Manifest = manifest
	w.Status = "running"
	return nil
}

func (m *Mock) TerminateWorkload(_ context.Context, deploymentID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	w, ok := m.workloads[deploymentID]
	if !ok {
		return fmt.Errorf("deployment %q is not deployed", deploymentID)
	}
	w.Status = "terminated"
	return nil
}

// WorkloadState returns a copy of the mock's current view of a deployment,
// if any -- used by cmd/mockclusteragent and tests to assert on what was
// actually applied.
func (m *Mock) GetWorkloadState(deploymentID string) (WorkloadState, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	w, ok := m.workloads[deploymentID]
	if !ok {
		return WorkloadState{}, false
	}
	return *w, true
}
