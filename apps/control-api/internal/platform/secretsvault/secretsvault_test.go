package secretsvault

import (
	"crypto/rand"
	"testing"
)

func testKey(t *testing.T) []byte {
	t.Helper()
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		t.Fatalf("generate test key: %v", err)
	}
	return key
}

func TestEncryptDecryptRoundTrip(t *testing.T) {
	v, err := New(testKey(t))
	if err != nil {
		t.Fatalf("new vault: %v", err)
	}
	ciphertext, err := v.Encrypt("sk-fictional-model-provider-api-key")
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	if ciphertext == "sk-fictional-model-provider-api-key" {
		t.Fatalf("ciphertext must not equal the plaintext")
	}
	plaintext, err := v.Decrypt(ciphertext)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	if plaintext != "sk-fictional-model-provider-api-key" {
		t.Fatalf("expected round-tripped plaintext, got %q", plaintext)
	}
}

func TestDecryptRejectsWrongKey(t *testing.T) {
	v1, err := New(testKey(t))
	if err != nil {
		t.Fatalf("new vault 1: %v", err)
	}
	v2, err := New(testKey(t))
	if err != nil {
		t.Fatalf("new vault 2: %v", err)
	}
	ciphertext, err := v1.Encrypt("secret-value")
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	if _, err := v2.Decrypt(ciphertext); err == nil {
		t.Fatalf("expected decryption with the wrong key to fail")
	}
}

func TestNewRejectsWrongKeyLength(t *testing.T) {
	if _, err := New([]byte("too-short")); err == nil {
		t.Fatalf("expected an error for a key that is not 32 bytes")
	}
}
