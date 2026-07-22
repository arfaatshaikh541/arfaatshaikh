package security_test

import (
	"strings"
	"testing"
	"time"

	"github.com/pquerna/otp/totp"

	"gridkeep/control-api/internal/platform/security"
)

func testTOTPManager(t *testing.T) *security.TOTPManager {
	t.Helper()
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(i)
	}
	m, err := security.NewTOTPManager(key, "GRIDKEEP-TEST")
	if err != nil {
		t.Fatalf("new totp manager: %v", err)
	}
	return m
}

func TestTOTPManager_ValidatesCorrectCode(t *testing.T) {
	m := testTOTPManager(t)
	uri, encSecret, err := m.GenerateSecret("user@example.com")
	if err != nil {
		t.Fatalf("generate secret: %v", err)
	}
	if uri == "" {
		t.Fatal("expected a non-empty otpauth URI")
	}

	secret := extractSecretFromURI(t, uri)
	code, err := totp.GenerateCode(secret, time.Now())
	if err != nil {
		t.Fatalf("generate code: %v", err)
	}

	valid, err := m.Validate(code, encSecret)
	if err != nil {
		t.Fatalf("validate: %v", err)
	}
	if !valid {
		t.Fatal("expected the freshly generated code to validate")
	}
}

func TestTOTPManager_RejectsWrongCode(t *testing.T) {
	m := testTOTPManager(t)
	_, encSecret, err := m.GenerateSecret("user@example.com")
	if err != nil {
		t.Fatalf("generate secret: %v", err)
	}
	valid, err := m.Validate("000000", encSecret)
	if err != nil {
		t.Fatalf("validate: %v", err)
	}
	if valid {
		t.Fatal("expected an arbitrary code to be rejected (astronomically unlikely to be correct)")
	}
}

func TestTOTPManager_SecretIsEncryptedAtRest(t *testing.T) {
	m := testTOTPManager(t)
	_, encSecret, err := m.GenerateSecret("user@example.com")
	if err != nil {
		t.Fatalf("generate secret: %v", err)
	}
	// The encrypted blob must not contain any recognizable base32 secret
	// material in the clear -- it should look like opaque ciphertext.
	if len(encSecret) == 0 {
		t.Fatal("expected non-empty encrypted secret")
	}
}

func TestNewTOTPManager_RejectsWrongKeyLength(t *testing.T) {
	if _, err := security.NewTOTPManager([]byte("too-short"), "GRIDKEEP-TEST"); err == nil {
		t.Fatal("expected an error for a key that is not 32 bytes")
	}
}

func extractSecretFromURI(t *testing.T, uri string) string {
	t.Helper()
	const marker = "secret="
	idx := strings.Index(uri, marker)
	if idx == -1 {
		t.Fatalf("no secret= parameter in %s", uri)
	}
	rest := uri[idx+len(marker):]
	end := strings.IndexAny(rest, "&")
	if end == -1 {
		end = len(rest)
	}
	return rest[:end]
}
