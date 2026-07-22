package security_test

import (
	"testing"

	"gridkeep/control-api/internal/platform/security"
)

func TestGenerateOpaqueToken_UniquePerCall(t *testing.T) {
	raw1, hash1, err := security.GenerateOpaqueToken(32)
	if err != nil {
		t.Fatalf("generate token 1: %v", err)
	}
	raw2, hash2, err := security.GenerateOpaqueToken(32)
	if err != nil {
		t.Fatalf("generate token 2: %v", err)
	}
	if raw1 == raw2 {
		t.Fatal("expected two generated tokens to differ")
	}
	if hash1 == hash2 {
		t.Fatal("expected two token hashes to differ")
	}
}

func TestGenerateOpaqueToken_HashIsConsistent(t *testing.T) {
	raw, hash, err := security.GenerateOpaqueToken(32)
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}
	if security.HashToken(raw) != hash {
		t.Fatal("expected HashToken(raw) to reproduce the same hash returned at generation time")
	}
}

func TestHashToken_DifferentInputsProduceDifferentHashes(t *testing.T) {
	if security.HashToken("token-a") == security.HashToken("token-b") {
		t.Fatal("expected different inputs to hash differently")
	}
}

func TestConstantTimeEquals(t *testing.T) {
	if !security.ConstantTimeEquals("abc", "abc") {
		t.Fatal("expected equal strings to compare equal")
	}
	if security.ConstantTimeEquals("abc", "abd") {
		t.Fatal("expected different strings to compare unequal")
	}
}
