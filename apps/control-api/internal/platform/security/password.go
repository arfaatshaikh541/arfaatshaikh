// Package security implements password hashing, opaque token generation and
// hashing, and TOTP MFA helpers. Nothing in this package ever logs or
// returns a secret value once it has been consumed.
package security

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"fmt"
	"strings"

	"golang.org/x/crypto/argon2"
)

// PasswordHasher hashes and verifies passwords using Argon2id with
// operator-configurable cost parameters (memory, iterations, parallelism).
type PasswordHasher struct {
	Memory      uint32
	Iterations  uint32
	Parallelism uint8
	SaltLength  uint32
	KeyLength   uint32
}

func NewPasswordHasher(memory, iterations uint32, parallelism uint8) *PasswordHasher {
	return &PasswordHasher{
		Memory:      memory,
		Iterations:  iterations,
		Parallelism: parallelism,
		SaltLength:  16,
		KeyLength:   32,
	}
}

// Hash returns an encoded Argon2id hash string in the form:
// $argon2id$v=19$m=<mem>,t=<iter>,p=<par>$<salt-b64>$<hash-b64>
func (h *PasswordHasher) Hash(password string) (string, error) {
	salt := make([]byte, h.SaltLength)
	if _, err := rand.Read(salt); err != nil {
		return "", fmt.Errorf("generate salt: %w", err)
	}

	hash := argon2.IDKey([]byte(password), salt, h.Iterations, h.Memory, h.Parallelism, h.KeyLength)

	encoded := fmt.Sprintf(
		"$argon2id$v=%d$m=%d,t=%d,p=%d$%s$%s",
		argon2.Version,
		h.Memory, h.Iterations, h.Parallelism,
		base64.RawStdEncoding.EncodeToString(salt),
		base64.RawStdEncoding.EncodeToString(hash),
	)
	return encoded, nil
}

// Verify checks a plaintext password against a previously encoded hash using
// constant-time comparison. It re-derives the hash using the parameters
// embedded in the stored value, so past hashes remain verifiable even if
// ARGON2_* configuration changes later.
func (h *PasswordHasher) Verify(password, encoded string) (bool, error) {
	parts := strings.Split(encoded, "$")
	if len(parts) != 6 || parts[1] != "argon2id" {
		return false, fmt.Errorf("unrecognized password hash format")
	}

	var version int
	if _, err := fmt.Sscanf(parts[2], "v=%d", &version); err != nil {
		return false, fmt.Errorf("parse version: %w", err)
	}

	var memory, iterations uint32
	var parallelism uint8
	if _, err := fmt.Sscanf(parts[3], "m=%d,t=%d,p=%d", &memory, &iterations, &parallelism); err != nil {
		return false, fmt.Errorf("parse params: %w", err)
	}

	salt, err := base64.RawStdEncoding.DecodeString(parts[4])
	if err != nil {
		return false, fmt.Errorf("decode salt: %w", err)
	}
	storedHash, err := base64.RawStdEncoding.DecodeString(parts[5])
	if err != nil {
		return false, fmt.Errorf("decode hash: %w", err)
	}

	computed := argon2.IDKey([]byte(password), salt, iterations, memory, parallelism, uint32(len(storedHash)))

	return subtle.ConstantTimeCompare(computed, storedHash) == 1, nil
}
