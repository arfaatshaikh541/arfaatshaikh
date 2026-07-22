-- Milestone 1: short-lived MFA step-up challenges issued after a password
-- check succeeds for a user with MFA enabled. A session is only created
-- once the corresponding TOTP code is verified against this challenge.

CREATE TABLE mfa_challenges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ
);
CREATE INDEX idx_mfa_challenges_user_id ON mfa_challenges(user_id);
