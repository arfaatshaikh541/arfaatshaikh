// Package billingprovider defines the narrow, provider-neutral billing
// integration boundary Milestone 11 ("Usage, Billing and Settlement")
// requires -- Provider is the abstraction the approved architecture's
// "billing-provider abstraction" requirement asks for, a fixed interface
// future adapters for a real payment/billing gateway (Stripe, Chargebee, an
// operator's own invoicing system) would each implement once.
//
// Like internal/platform/attestation.Provider (and unlike
// internal/platform/clusteradapter/networkadapter, which are agent-side),
// Provider is verifier/integration-side: control-api itself holds and
// calls an implementation directly, because syncing an invoice or
// settlement to an external billing system is inherently something the
// platform itself does, not something delegated to a cluster agent.
//
// The only implementation in this codebase is MockProvider. It has no real
// external system to integrate with in this environment (no payment
// gateway is reachable from this sandbox, the same category of constraint
// as MinIO/Docker Hub) -- it synchronously fabricates a deterministic
// external reference and reports success, making no claim of having
// actually moved money or contacted any real billing system. A real
// provider (calling out to an actual payment/billing API, verifying
// webhook signatures, handling asynchronous settlement) is future work for
// whichever milestone integrates a real billing gateway.
package billingprovider

import (
	"context"
	"fmt"

	"github.com/google/uuid"
)

// Invoice is the narrow, provider-agnostic view of an invoice or
// settlement a Provider needs to sync -- passed by value so this package
// has no database dependency of its own, mirroring
// internal/platform/attestation's Policy/Evidence pattern.
type Invoice struct {
	ID       uuid.UUID
	Total    float64
	Currency string
}

// SyncResult is what a Provider reports back. Provider.Sync never has side
// effects beyond its return value -- persisting external_ref and recording
// a billing_provider_events row is the caller's job
// (internal/modules/billing), keeping this package a pure integration
// primitive, easy to swap for a real gateway later without touching any
// persistence or authorization code.
type SyncResult struct {
	ExternalRef string
	Synced      bool
}

// Provider syncs an invoice or settlement to an external billing system.
type Provider interface {
	Sync(ctx context.Context, invoice Invoice) (SyncResult, error)
}

// MockProvider is a clearly-labelled stand-in for a real billing gateway --
// exactly what the approved architecture's "mock billing provider"
// requirement asks for. It synchronously "syncs" every invoice
// successfully; there is no failure mode to simulate against, since there
// is no real gateway behind it whose failure modes (network errors,
// declined payments, rate limits) would be meaningful to fabricate.
type MockProvider struct{}

func NewMockProvider() *MockProvider { return &MockProvider{} }

func (p *MockProvider) Sync(_ context.Context, invoice Invoice) (SyncResult, error) {
	return SyncResult{ExternalRef: fmt.Sprintf("mock-ext-%s", invoice.ID), Synced: true}, nil
}
