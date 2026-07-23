-- Milestone 2: singleton row holding GRIDKEEP's local development
-- certificate authority (see internal/platform/pki). The CA private key is
-- encrypted at rest with AES-256-GCM using PKI_CA_ENCRYPTION_KEY (same
-- pattern as MFA_ENCRYPTION_KEY for TOTP secrets) -- a stand-in for a
-- Vault-PKI-issued intermediate CA in production, exactly as documented for
-- MFA secret encryption in Milestone 1.
--
-- This table is never read by any HTTP route -- only internal/platform/pki
-- touches it -- and carries no tenant/operator ownership, so no RLS applies
-- (same reasoning as `roles`/`permissions`).
--
-- The `singleton` column plus its UNIQUE + CHECK constraint is the standard
-- Postgres idiom for enforcing "this table holds at most one row."

CREATE TABLE platform_ca (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    singleton             BOOLEAN NOT NULL DEFAULT TRUE UNIQUE CHECK (singleton),
    certificate_pem       TEXT NOT NULL,
    encrypted_private_key TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
