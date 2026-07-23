// Package pki implements GRIDKEEP's local development certificate
// authority: a real, working X.509 CA (crypto/x509, not a stub) that issues
// short-lived client certificates to operator agents from CSRs they
// generate themselves, and verifies signatures those agents make with the
// resulting certificate's key pair. It is an explicit, documented stand-in
// for a Vault-PKI-issued intermediate CA in production (see
// docs/adr/0007-local-development-certificate-authority.md) -- everything
// it does (key generation, signing, signature verification) is real
// cryptography; only the "who operates the root of trust" question differs
// from the target production architecture.
package pki

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"math/big"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const caValidity = 10 * 365 * 24 * time.Hour // 10 years -- this is the root, not a leaf.

// CA holds the loaded (or freshly generated) certificate authority key
// pair. It is safe for concurrent use — signing only reads the key.
type CA struct {
	cert *x509.Certificate
	key  *ecdsa.PrivateKey
}

// LoadOrCreate returns the single, persistent GRIDKEEP local CA, generating
// and durably storing one (AES-256-GCM encrypted at rest) on first use if
// none exists yet. Safe under concurrent startup: a unique constraint on
// the singleton row means at most one process's generated CA is ever kept,
// and every caller re-reads whichever row won.
func LoadOrCreate(ctx context.Context, pool *pgxpool.Pool, encryptionKey []byte) (*CA, error) {
	if ca, ok, err := load(ctx, pool, encryptionKey); err != nil {
		return nil, err
	} else if ok {
		return ca, nil
	}

	certPEM, keyPEM, err := generateSelfSigned()
	if err != nil {
		return nil, fmt.Errorf("generate CA: %w", err)
	}
	encryptedKey, err := encrypt(encryptionKey, keyPEM)
	if err != nil {
		return nil, fmt.Errorf("encrypt CA private key: %w", err)
	}
	if _, err := pool.Exec(ctx, `
		INSERT INTO platform_ca (certificate_pem, encrypted_private_key)
		VALUES ($1, $2)
		ON CONFLICT (singleton) DO NOTHING
	`, certPEM, encryptedKey); err != nil {
		return nil, fmt.Errorf("persist CA: %w", err)
	}

	ca, ok, err := load(ctx, pool, encryptionKey)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, fmt.Errorf("CA row missing immediately after insert")
	}
	return ca, nil
}

func load(ctx context.Context, pool *pgxpool.Pool, encryptionKey []byte) (*CA, bool, error) {
	var certPEM, encryptedKey string
	err := pool.QueryRow(ctx, `SELECT certificate_pem, encrypted_private_key FROM platform_ca WHERE singleton = TRUE`).
		Scan(&certPEM, &encryptedKey)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, false, nil
		}
		return nil, false, fmt.Errorf("load CA: %w", err)
	}

	keyPEM, err := decrypt(encryptionKey, encryptedKey)
	if err != nil {
		return nil, false, fmt.Errorf("decrypt CA private key: %w", err)
	}

	cert, err := parseCertPEM(certPEM)
	if err != nil {
		return nil, false, fmt.Errorf("parse CA certificate: %w", err)
	}
	key, err := parseECDSAKeyPEM(keyPEM)
	if err != nil {
		return nil, false, fmt.Errorf("parse CA private key: %w", err)
	}
	return &CA{cert: cert, key: key}, true, nil
}

func generateSelfSigned() (certPEM, keyPEM string, err error) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return "", "", fmt.Errorf("generate CA key: %w", err)
	}
	serial, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
	if err != nil {
		return "", "", fmt.Errorf("generate serial: %w", err)
	}
	template := &x509.Certificate{
		SerialNumber:          serial,
		Subject:               pkix.Name{CommonName: "GRIDKEEP Local Development CA", Organization: []string{"GRIDKEEP"}},
		NotBefore:             time.Now().Add(-5 * time.Minute),
		NotAfter:              time.Now().Add(caValidity),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign | x509.KeyUsageDigitalSignature,
		BasicConstraintsValid: true,
		IsCA:                  true,
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		return "", "", fmt.Errorf("create CA certificate: %w", err)
	}
	return string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})), encodeECDSAKeyPEM(key), nil
}
