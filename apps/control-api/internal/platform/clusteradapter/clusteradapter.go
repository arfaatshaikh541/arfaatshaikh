// Package clusteradapter defines the narrow, named set of operations a
// cluster agent may perform against the Kubernetes cluster it runs
// alongside -- namespace creation, resource quotas, network policies, and
// security contexts. This interface *is* the delegated-access boundary the
// approved architecture requires ("do not give the central control plane
// unrestricted cluster-admin access"; "use delegated, policy-restricted
// access"): there is no method here for arbitrary manifest application,
// no method that takes a raw Kubernetes API request, and control-api
// itself never holds a kubeconfig or calls any of this directly -- only a
// cluster agent (Milestone 6's cmd/mockclusteragent today; a real daemon
// running inside the operator's cluster in production) does, and only
// through this exact, reviewable method set.
//
// The only implementation in this codebase is the in-memory Mock below.
// Milestone 6 does not integrate a real Kubernetes client (client-go) --
// there is no live cluster in this environment to integrate against, and
// doing so would not be exercised by anything. A real implementation
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

type ClusterAdapter interface {
	CreateNamespace(ctx context.Context, name string) error
	ApplyResourceQuota(ctx context.Context, namespace string, quota map[string]any) error
	ApplyNetworkPolicy(ctx context.Context, namespace string, policy map[string]any) error
	ApplySecurityContext(ctx context.Context, namespace string, securityContext map[string]any) error
	Health(ctx context.Context) (Health, error)
}

// Mock is an in-memory ClusterAdapter -- it proves the protocol (a
// namespace must exist before a quota/policy/security-context can be
// applied to it; every operation is scoped to a namespace, never
// cluster-wide) without touching a real Kubernetes API. Safe for
// concurrent use.
type Mock struct {
	mu               sync.Mutex
	namespaces       map[string]bool
	resourceQuotas   map[string]map[string]any
	networkPolicies  map[string]map[string]any
	securityContexts map[string]map[string]any
}

func NewMock() *Mock {
	return &Mock{
		namespaces:       make(map[string]bool),
		resourceQuotas:   make(map[string]map[string]any),
		networkPolicies:  make(map[string]map[string]any),
		securityContexts: make(map[string]map[string]any),
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
