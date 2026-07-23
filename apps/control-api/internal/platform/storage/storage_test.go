package storage

import (
	"strings"
	"testing"

	"github.com/google/uuid"
)

func TestObjectKey_TenantIsolatedAndNonGuessable(t *testing.T) {
	tenantA := uuid.New()
	tenantB := uuid.New()

	keyA1 := ObjectKey(tenantA, nil)
	keyA2 := ObjectKey(tenantA, nil)
	keyB := ObjectKey(tenantB, nil)

	if !strings.HasPrefix(keyA1, "tenants/"+tenantA.String()+"/") {
		t.Fatalf("expected key to be prefixed with tenant path, got %q", keyA1)
	}
	if keyA1 == keyA2 {
		t.Fatalf("expected two calls for the same tenant to produce different, non-guessable keys, got the same key twice: %q", keyA1)
	}
	if strings.HasPrefix(keyB, "tenants/"+tenantA.String()) {
		t.Fatalf("expected tenant B's key not to share tenant A's prefix, got %q", keyB)
	}
}

func TestObjectKey_OperatorIsolated(t *testing.T) {
	tenantID := uuid.New()
	operatorID := uuid.New()

	key := ObjectKey(tenantID, &operatorID)

	wantPrefix := "tenants/" + tenantID.String() + "/operators/" + operatorID.String() + "/"
	if !strings.HasPrefix(key, wantPrefix) {
		t.Fatalf("expected key %q to have prefix %q", key, wantPrefix)
	}
}
