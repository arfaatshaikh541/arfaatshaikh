package identity

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// conn is satisfied by both *pgxpool.Pool and pgx.Tx, letting repository
// functions run either standalone or inside a transaction the caller
// controls (e.g. so an audit event commits atomically with the change it
// describes).
type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

func createUser(ctx context.Context, c conn, email, passwordHash string) (User, error) {
	var u User
	err := c.QueryRow(ctx, `
		INSERT INTO users (email, password_hash) VALUES ($1, $2)
		RETURNING id, email, password_hash, email_verified_at, status, mfa_enabled, created_at
	`, email, passwordHash).Scan(&u.ID, &u.Email, &u.PasswordHash, &u.EmailVerifiedAt, &u.Status, &u.MFAEnabled, &u.CreatedAt)
	if err != nil {
		return User{}, fmt.Errorf("insert user: %w", err)
	}
	return u, nil
}

func getUserByEmail(ctx context.Context, c conn, email string) (User, bool, error) {
	var u User
	err := c.QueryRow(ctx, `
		SELECT id, email, password_hash, email_verified_at, status, mfa_enabled, created_at
		FROM users WHERE email = $1
	`, email).Scan(&u.ID, &u.Email, &u.PasswordHash, &u.EmailVerifiedAt, &u.Status, &u.MFAEnabled, &u.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return User{}, false, nil
		}
		return User{}, false, fmt.Errorf("get user by email: %w", err)
	}
	return u, true, nil
}

func getUserByID(ctx context.Context, c conn, id uuid.UUID) (User, bool, error) {
	var u User
	err := c.QueryRow(ctx, `
		SELECT id, email, password_hash, email_verified_at, status, mfa_enabled, created_at
		FROM users WHERE id = $1
	`, id).Scan(&u.ID, &u.Email, &u.PasswordHash, &u.EmailVerifiedAt, &u.Status, &u.MFAEnabled, &u.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return User{}, false, nil
		}
		return User{}, false, fmt.Errorf("get user by id: %w", err)
	}
	return u, true, nil
}

func markEmailVerified(ctx context.Context, c conn, userID uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE users SET email_verified_at = now(), updated_at = now() WHERE id = $1`, userID)
	if err != nil {
		return fmt.Errorf("mark email verified: %w", err)
	}
	return nil
}

func updatePasswordHash(ctx context.Context, c conn, userID uuid.UUID, hash string) error {
	_, err := c.Exec(ctx, `UPDATE users SET password_hash = $2, updated_at = now() WHERE id = $1`, userID, hash)
	if err != nil {
		return fmt.Errorf("update password hash: %w", err)
	}
	return nil
}

func setMFAEnabled(ctx context.Context, c conn, userID uuid.UUID, enabled bool) error {
	_, err := c.Exec(ctx, `UPDATE users SET mfa_enabled = $2, updated_at = now() WHERE id = $1`, userID, enabled)
	if err != nil {
		return fmt.Errorf("set mfa enabled: %w", err)
	}
	return nil
}

func insertEmailVerificationToken(ctx context.Context, c conn, userID uuid.UUID, tokenHash string, ttl time.Duration) error {
	_, err := c.Exec(ctx, `
		INSERT INTO email_verification_tokens (user_id, token_hash, expires_at)
		VALUES ($1, $2, now() + ($3 * interval '1 second'))
	`, userID, tokenHash, ttl.Seconds())
	if err != nil {
		return fmt.Errorf("insert email verification token: %w", err)
	}
	return nil
}

func consumeEmailVerificationToken(ctx context.Context, c conn, tokenHash string) (uuid.UUID, bool, error) {
	var userID uuid.UUID
	err := c.QueryRow(ctx, `
		UPDATE email_verification_tokens
		SET consumed_at = now()
		WHERE token_hash = $1 AND consumed_at IS NULL AND expires_at > now()
		RETURNING user_id
	`, tokenHash).Scan(&userID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("consume email verification token: %w", err)
	}
	return userID, true, nil
}

func insertPasswordResetToken(ctx context.Context, c conn, userID uuid.UUID, tokenHash string, ttl time.Duration) error {
	_, err := c.Exec(ctx, `
		INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
		VALUES ($1, $2, now() + ($3 * interval '1 second'))
	`, userID, tokenHash, ttl.Seconds())
	if err != nil {
		return fmt.Errorf("insert password reset token: %w", err)
	}
	return nil
}

func consumePasswordResetToken(ctx context.Context, c conn, tokenHash string) (uuid.UUID, bool, error) {
	var userID uuid.UUID
	err := c.QueryRow(ctx, `
		UPDATE password_reset_tokens
		SET consumed_at = now()
		WHERE token_hash = $1 AND consumed_at IS NULL AND expires_at > now()
		RETURNING user_id
	`, tokenHash).Scan(&userID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("consume password reset token: %w", err)
	}
	return userID, true, nil
}

func recordLoginAttempt(ctx context.Context, c conn, email, ip string, succeeded bool) error {
	_, err := c.Exec(ctx, `
		INSERT INTO login_attempts (email, ip_address, succeeded) VALUES ($1, $2, $3)
	`, email, ip, succeeded)
	if err != nil {
		return fmt.Errorf("record login attempt: %w", err)
	}
	return nil
}

func countRecentFailedAttempts(ctx context.Context, c conn, email string, window time.Duration) (int, error) {
	var count int
	err := c.QueryRow(ctx, `
		SELECT count(*) FROM login_attempts
		WHERE email = $1 AND succeeded = FALSE AND created_at > now() - ($2 * interval '1 second')
	`, email, window.Seconds()).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("count recent failed attempts: %w", err)
	}
	return count, nil
}

func createSession(ctx context.Context, c conn, userID uuid.UUID, tokenHash, ip, userAgent string, ttl time.Duration) (uuid.UUID, error) {
	var id uuid.UUID
	err := c.QueryRow(ctx, `
		INSERT INTO sessions (user_id, token_hash, ip_address, user_agent, expires_at)
		VALUES ($1, $2, $3, $4, now() + ($5 * interval '1 second'))
		RETURNING id
	`, userID, tokenHash, ip, userAgent, ttl.Seconds()).Scan(&id)
	if err != nil {
		return uuid.Nil, fmt.Errorf("create session: %w", err)
	}
	return id, nil
}

func getSessionByTokenHash(ctx context.Context, c conn, tokenHash string) (Session, bool, error) {
	var s Session
	err := c.QueryRow(ctx, `
		SELECT id, user_id, expires_at, revoked_at, step_up_at
		FROM sessions WHERE token_hash = $1
	`, tokenHash).Scan(&s.ID, &s.UserID, &s.ExpiresAt, &s.RevokedAt, &s.StepUpAt)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Session{}, false, nil
		}
		return Session{}, false, fmt.Errorf("get session by token hash: %w", err)
	}
	return s, true, nil
}

func touchSession(ctx context.Context, c conn, sessionID uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE sessions SET last_seen_at = now() WHERE id = $1`, sessionID)
	if err != nil {
		return fmt.Errorf("touch session: %w", err)
	}
	return nil
}

func markSessionStepUp(ctx context.Context, c conn, sessionID uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE sessions SET step_up_at = now() WHERE id = $1`, sessionID)
	if err != nil {
		return fmt.Errorf("mark session step-up: %w", err)
	}
	return nil
}

func revokeSession(ctx context.Context, c conn, sessionID uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE sessions SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL`, sessionID)
	if err != nil {
		return fmt.Errorf("revoke session: %w", err)
	}
	return nil
}

func revokeAllUserSessions(ctx context.Context, c conn, userID uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE sessions SET revoked_at = now() WHERE user_id = $1 AND revoked_at IS NULL`, userID)
	if err != nil {
		return fmt.Errorf("revoke all user sessions: %w", err)
	}
	return nil
}

func createMFAChallenge(ctx context.Context, c conn, userID uuid.UUID, tokenHash string, ttl time.Duration) error {
	_, err := c.Exec(ctx, `
		INSERT INTO mfa_challenges (user_id, token_hash, expires_at)
		VALUES ($1, $2, now() + ($3 * interval '1 second'))
	`, userID, tokenHash, ttl.Seconds())
	if err != nil {
		return fmt.Errorf("create mfa challenge: %w", err)
	}
	return nil
}

func consumeMFAChallenge(ctx context.Context, c conn, tokenHash string) (uuid.UUID, bool, error) {
	var userID uuid.UUID
	err := c.QueryRow(ctx, `
		UPDATE mfa_challenges
		SET consumed_at = now()
		WHERE token_hash = $1 AND consumed_at IS NULL AND expires_at > now()
		RETURNING user_id
	`, tokenHash).Scan(&userID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return uuid.Nil, false, nil
		}
		return uuid.Nil, false, fmt.Errorf("consume mfa challenge: %w", err)
	}
	return userID, true, nil
}

func upsertMFASecret(ctx context.Context, c conn, userID uuid.UUID, encryptedSecret string) error {
	_, err := c.Exec(ctx, `
		INSERT INTO mfa_totp_secrets (user_id, encrypted_secret)
		VALUES ($1, $2)
		ON CONFLICT (user_id) DO UPDATE SET encrypted_secret = EXCLUDED.encrypted_secret, confirmed_at = NULL
	`, userID, encryptedSecret)
	if err != nil {
		return fmt.Errorf("upsert mfa secret: %w", err)
	}
	return nil
}

func getMFASecret(ctx context.Context, c conn, userID uuid.UUID) (string, bool, error) {
	var secret string
	err := c.QueryRow(ctx, `SELECT encrypted_secret FROM mfa_totp_secrets WHERE user_id = $1`, userID).Scan(&secret)
	if err != nil {
		if err == pgx.ErrNoRows {
			return "", false, nil
		}
		return "", false, fmt.Errorf("get mfa secret: %w", err)
	}
	return secret, true, nil
}

func confirmMFASecret(ctx context.Context, c conn, userID uuid.UUID) error {
	_, err := c.Exec(ctx, `UPDATE mfa_totp_secrets SET confirmed_at = now() WHERE user_id = $1`, userID)
	if err != nil {
		return fmt.Errorf("confirm mfa secret: %w", err)
	}
	return nil
}

func deleteMFASecret(ctx context.Context, c conn, userID uuid.UUID) error {
	_, err := c.Exec(ctx, `DELETE FROM mfa_totp_secrets WHERE user_id = $1`, userID)
	if err != nil {
		return fmt.Errorf("delete mfa secret: %w", err)
	}
	return nil
}
