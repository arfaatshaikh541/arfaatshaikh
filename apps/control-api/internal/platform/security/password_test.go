package security_test

import (
	"testing"

	"gridkeep/control-api/internal/platform/security"
)

func TestPasswordHasher_VerifyCorrectPassword(t *testing.T) {
	h := security.NewPasswordHasher(19456, 2, 1)
	hash, err := h.Hash("CorrectHorseBatteryStaple1")
	if err != nil {
		t.Fatalf("hash: %v", err)
	}
	ok, err := h.Verify("CorrectHorseBatteryStaple1", hash)
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if !ok {
		t.Fatal("expected correct password to verify")
	}
}

func TestPasswordHasher_RejectsWrongPassword(t *testing.T) {
	h := security.NewPasswordHasher(19456, 2, 1)
	hash, err := h.Hash("CorrectHorseBatteryStaple1")
	if err != nil {
		t.Fatalf("hash: %v", err)
	}
	ok, err := h.Verify("WrongPassword", hash)
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if ok {
		t.Fatal("expected wrong password to fail verification")
	}
}

func TestPasswordHasher_SameInputProducesDifferentHashes(t *testing.T) {
	h := security.NewPasswordHasher(19456, 2, 1)
	hash1, err := h.Hash("SamePassword123456")
	if err != nil {
		t.Fatalf("hash1: %v", err)
	}
	hash2, err := h.Hash("SamePassword123456")
	if err != nil {
		t.Fatalf("hash2: %v", err)
	}
	if hash1 == hash2 {
		t.Fatal("expected two hashes of the same password to differ (random salt)")
	}
	for _, hash := range []string{hash1, hash2} {
		ok, err := h.Verify("SamePassword123456", hash)
		if err != nil || !ok {
			t.Fatalf("expected hash %q to verify, ok=%v err=%v", hash, ok, err)
		}
	}
}

func TestPasswordHasher_RejectsMalformedHash(t *testing.T) {
	h := security.NewPasswordHasher(19456, 2, 1)
	if _, err := h.Verify("anything", "not-a-valid-hash"); err == nil {
		t.Fatal("expected an error for a malformed stored hash")
	}
}
