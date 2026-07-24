package billingprovider

import (
	"context"
	"testing"

	"github.com/google/uuid"
)

func TestMockProviderSyncsDeterministically(t *testing.T) {
	ctx := context.Background()
	p := NewMockProvider()

	id := uuid.New()
	result, err := p.Sync(ctx, Invoice{ID: id, Total: 42.50, Currency: "USD"})
	if err != nil {
		t.Fatalf("sync invoice: %v", err)
	}
	if !result.Synced {
		t.Fatalf("expected synced=true, got %v", result)
	}
	if result.ExternalRef == "" {
		t.Fatalf("expected a non-empty external reference")
	}

	// Syncing the same invoice id again must produce the identical
	// external reference -- deterministic, not random, so a caller can
	// safely retry a sync without producing a second, different reference.
	second, err := p.Sync(ctx, Invoice{ID: id, Total: 42.50, Currency: "USD"})
	if err != nil {
		t.Fatalf("re-sync invoice: %v", err)
	}
	if second.ExternalRef != result.ExternalRef {
		t.Fatalf("expected the same external reference on retry, got %q vs %q", result.ExternalRef, second.ExternalRef)
	}
}
