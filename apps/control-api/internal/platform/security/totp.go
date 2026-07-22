package security

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"time"

	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"
)

// TOTPManager generates and verifies time-based one-time-password secrets
// for MFA enrollment. Secrets are encrypted at rest with AES-256-GCM using a
// key supplied by the environment (a stand-in for a Vault/KMS-issued
// data-encryption key in production — see docs/adr for the migration path).
type TOTPManager struct {
	encryptionKey []byte // 32 bytes for AES-256
	issuer        string
}

func NewTOTPManager(encryptionKey []byte, issuer string) (*TOTPManager, error) {
	if len(encryptionKey) != 32 {
		return nil, fmt.Errorf("MFA encryption key must be 32 bytes, got %d", len(encryptionKey))
	}
	return &TOTPManager{encryptionKey: encryptionKey, issuer: issuer}, nil
}

// GenerateSecret creates a new TOTP secret and returns the otpauth:// URI
// (for QR-code rendering by the client) alongside the encrypted secret to
// persist. The raw secret is never persisted or logged in plaintext.
func (m *TOTPManager) GenerateSecret(accountEmail string) (otpauthURI string, encryptedSecret string, err error) {
	key, err := totp.Generate(totp.GenerateOpts{
		Issuer:      m.issuer,
		AccountName: accountEmail,
	})
	if err != nil {
		return "", "", fmt.Errorf("generate totp key: %w", err)
	}

	enc, err := m.encrypt(key.Secret())
	if err != nil {
		return "", "", err
	}

	return key.URL(), enc, nil
}

func (m *TOTPManager) Validate(code string, encryptedSecret string) (bool, error) {
	secret, err := m.decrypt(encryptedSecret)
	if err != nil {
		return false, err
	}
	return totp.ValidateCustom(code, secret, time.Now(), totp.ValidateOpts{
		Period:    30,
		Skew:      1,
		Digits:    otp.DigitsSix,
		Algorithm: otp.AlgorithmSHA1,
	})
}

func (m *TOTPManager) encrypt(plaintext string) (string, error) {
	block, err := aes.NewCipher(m.encryptionKey)
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

func (m *TOTPManager) decrypt(encoded string) (string, error) {
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return "", fmt.Errorf("decode ciphertext: %w", err)
	}
	block, err := aes.NewCipher(m.encryptionKey)
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
