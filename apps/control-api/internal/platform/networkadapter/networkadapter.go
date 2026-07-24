// Package networkadapter defines the narrow, named set of operations a
// cluster agent may perform to provision a network service the approved
// architecture's Milestone 9 ("Network and Edge Services") scope requires
// -- mirroring internal/platform/clusteradapter's shape and rationale
// exactly: this interface *is* the delegated-access boundary ("GRIDKEEP
// should request and verify authorised network services through operator
// connectors," "do not replace operator network control systems"), not a
// policy document. control-api itself never imports this package or calls
// any of it directly -- only a cluster agent (cmd/mockclusteragent today; a
// real daemon running inside the operator's cluster in production) does,
// and only through this exact, reviewable method set, keyed by
// reservation ID, never by a raw request a caller could point at something
// else.
//
// The only implementation in this codebase is the in-memory Mock below.
// This milestone does not integrate any real network-orchestration system
// (SD-WAN controller, 5G core, physical network-slice provisioner) --
// there is no live network fabric in this environment to integrate
// against. A real implementation, scoped to whatever narrow API surface an
// operator's own network control system exposes, is future work for
// whichever milestone stands up a real network-integration daemon.
package networkadapter

import (
	"context"
	"fmt"
	"sync"
)

// ServiceState is a read-only snapshot of what the mock adapter believes is
// currently provisioned -- used by cmd/mockclusteragent and tests to
// report/assert on adapter-side state without exposing the adapter's
// internal map directly.
type ServiceState struct {
	BandwidthGbps float64
	ServiceClass  string
	Status        string // "provisioned", "released"
}

type Adapter interface {
	ProvisionService(ctx context.Context, reservationID string, bandwidthGbps float64, serviceClass string) error
	ReleaseService(ctx context.Context, reservationID string) error
}

// Mock is an in-memory Adapter -- it proves the protocol (releasing a
// service that was never provisioned is rejected, every operation is
// scoped to one reservation ID, never a raw network configuration) without
// touching any real network-orchestration system. Safe for concurrent use.
type Mock struct {
	mu       sync.Mutex
	services map[string]*ServiceState
}

func NewMock() *Mock {
	return &Mock{services: make(map[string]*ServiceState)}
}

// ProvisionService records the reservation as provisioned, overwriting any
// prior state for the same reservation ID -- re-provisioning (e.g. after a
// retry) is valid and idempotent from the caller's perspective, the same
// "unconditional set" simplicity internal/platform/clusteradapter.Mock's
// DeployWorkload uses.
func (m *Mock) ProvisionService(_ context.Context, reservationID string, bandwidthGbps float64, serviceClass string) error {
	if bandwidthGbps <= 0 {
		return fmt.Errorf("bandwidth must be positive, got %v", bandwidthGbps)
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.services[reservationID] = &ServiceState{BandwidthGbps: bandwidthGbps, ServiceClass: serviceClass, Status: "provisioned"}
	return nil
}

func (m *Mock) ReleaseService(_ context.Context, reservationID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	s, ok := m.services[reservationID]
	if !ok {
		return fmt.Errorf("reservation %q is not provisioned", reservationID)
	}
	s.Status = "released"
	return nil
}

// GetServiceState returns a copy of the mock's current view of a
// reservation, if any -- used by cmd/mockclusteragent and tests to assert
// on what was actually applied.
func (m *Mock) GetServiceState(reservationID string) (ServiceState, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	s, ok := m.services[reservationID]
	if !ok {
		return ServiceState{}, false
	}
	return *s, true
}
