package pki

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdsa"
	"crypto/rand"
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"fmt"
)

// encrypt/decrypt use the exact same AES-256-GCM construction as
// security.TOTPManager (see internal/platform/security/totp.go) -- a
// 32-byte key, random per-call nonce prepended to the ciphertext. Kept as
// unexported package-local functions here (rather than importing the
// security package) to avoid a platform-to-platform import for what is a
// handful of standard-library lines.

func encrypt(key []byte, plaintext string) (string, error) {
	if len(key) != 32 {
		return "", fmt.Errorf("encryption key must be 32 bytes, got %d", len(key))
	}
	block, err := aes.NewCipher(key)
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

func decrypt(key []byte, encoded string) (string, error) {
	if len(key) != 32 {
		return "", fmt.Errorf("encryption key must be 32 bytes, got %d", len(key))
	}
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return "", fmt.Errorf("decode ciphertext: %w", err)
	}
	block, err := aes.NewCipher(key)
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

func parseCertPEM(certPEM string) (*x509.Certificate, error) {
	block, _ := pem.Decode([]byte(certPEM))
	if block == nil || block.Type != "CERTIFICATE" {
		return nil, fmt.Errorf("not a PEM-encoded certificate")
	}
	return x509.ParseCertificate(block.Bytes)
}

func parseECDSAKeyPEM(keyPEM string) (*ecdsa.PrivateKey, error) {
	block, _ := pem.Decode([]byte(keyPEM))
	if block == nil || block.Type != "EC PRIVATE KEY" {
		return nil, fmt.Errorf("not a PEM-encoded EC private key")
	}
	return x509.ParseECPrivateKey(block.Bytes)
}

func encodeECDSAKeyPEM(key *ecdsa.PrivateKey) string {
	der, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		// key was just generated in-process by this package with a fixed,
		// always-marshalable curve — a marshal failure here is a stdlib
		// invariant violation, not a runtime condition callers can act on.
		panic(fmt.Sprintf("marshal freshly generated EC key: %v", err))
	}
	return string(pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: der}))
}
