// Package secretsvault provides envelope encryption at rest for workload
// secret values ("secure secrets" in Milestone 7's approved build scope).
// This is an explicit, documented stand-in for a HashiCorp Vault-issued
// data-encryption key in production, exactly the same relationship
// internal/platform/pki has to a Vault-issued intermediate CA (see ADR
// 0007) and internal/platform/security's TOTPManager has to Vault/KMS for
// MFA secrets -- the cryptography (AES-256-GCM, a random nonce per
// encryption) is real; only "who holds the root key" differs from the
// target production architecture. A real Vault-backed implementation
// (dynamic secrets, envelope encryption via Vault's transit engine, key
// rotation) is future work once this environment can reach a real Vault
// instance.
//
// Vault holds exactly one key with exactly one job: decrypting values it
// encrypted itself. Nothing in this codebase ever returns a decrypted
// value through a session-authenticated API response -- see
// internal/modules/deployments, which only ever decrypts a value to hand
// to the one cluster agent actually running the deployment that
// referenced it, over a certificate-authenticated channel.
package secretsvault

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"fmt"
)

// Vault encrypts and decrypts workload secret values with a single
// AES-256 key supplied by the environment.
type Vault struct {
	encryptionKey []byte // 32 bytes for AES-256
}

func New(encryptionKey []byte) (*Vault, error) {
	if len(encryptionKey) != 32 {
		return nil, fmt.Errorf("secrets vault encryption key must be 32 bytes, got %d", len(encryptionKey))
	}
	return &Vault{encryptionKey: encryptionKey}, nil
}

// Encrypt returns an opaque, base64-encoded ciphertext safe to persist in
// workload_secrets.encrypted_value. A fresh random nonce is generated per
// call and prepended to the ciphertext, matching the exact construction
// internal/platform/pki and internal/platform/security's TOTPManager
// already use for their own at-rest secrets.
func (v *Vault) Encrypt(plaintext string) (string, error) {
	block, err := aes.NewCipher(v.encryptionKey)
	if err != nil {
		return "", fmt.Errorf("init cipher: %w", err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("init gcm: %w", err)
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := rand.Read(nonce); err != nil {
		return "", fmt.Errorf("generate nonce: %w", err)
	}
	sealed := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return base64.StdEncoding.EncodeToString(sealed), nil
}

// Decrypt reverses Encrypt. Callers must only ever hand the result to the
// one recipient authorized to see it (see the package doc comment) --
// Decrypt itself has no way to enforce that; it is a pure cryptographic
// primitive, not an authorization control.
func (v *Vault) Decrypt(encoded string) (string, error) {
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return "", fmt.Errorf("decode ciphertext: %w", err)
	}
	block, err := aes.NewCipher(v.encryptionKey)
	if err != nil {
		return "", fmt.Errorf("init cipher: %w", err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("init gcm: %w", err)
	}
	nonceSize := gcm.NonceSize()
	if len(raw) < nonceSize {
		return "", fmt.Errorf("ciphertext too short")
	}
	nonce, ciphertext := raw[:nonceSize], raw[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return "", fmt.Errorf("decrypt: %w", err)
	}
	return string(plaintext), nil
}
