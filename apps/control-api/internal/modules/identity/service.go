// Package identity implements registration, email verification, Argon2id
// authentication, sessions, password reset, login-attempt lockout, and TOTP
// MFA. Every credential is hashed or encrypted at rest; raw secrets are
// handed to the client exactly once (cookie, emailed link, QR payload) and
// never logged or persisted in plaintext.
package identity

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/mailer"
	"gridkeep/control-api/internal/platform/security"
)

var (
	ErrEmailAlreadyRegistered = errors.New("email already registered")
	ErrInvalidCredentials     = errors.New("invalid email or password")
	ErrAccountLocked          = errors.New("account temporarily locked due to repeated failed logins")
	ErrEmailNotVerified       = errors.New("email address is not verified")
	ErrInvalidToken           = errors.New("invalid or expired token")
	ErrInvalidMFACode         = errors.New("invalid mfa code")
	ErrMFAAlreadyEnabled      = errors.New("mfa is already enabled")
	ErrMFANotEnrolled         = errors.New("mfa is not enrolled")
)

type Config struct {
	SessionTTL            time.Duration
	StepUpTTL             time.Duration
	EmailVerificationTTL  time.Duration
	PasswordResetTTL      time.Duration
	MFAChallengeTTL       time.Duration
	MFAMaxAttempts        int
	LoginLockoutThreshold int
	LoginLockoutWindow    time.Duration
	PublicBaseURL         string
}

type Service struct {
	store  *dbpkg.Store
	hasher *security.PasswordHasher
	totp   *security.TOTPManager
	mailer *mailer.Mailer
	cfg    Config
}

func NewService(store *dbpkg.Store, hasher *security.PasswordHasher, totp *security.TOTPManager, m *mailer.Mailer, cfg Config) *Service {
	return &Service{store: store, hasher: hasher, totp: totp, mailer: m, cfg: cfg}
}

// systemTx opens an account-level transaction (no tenant/operator context).
// PlatformBypass is used here purely so audit_events inserts satisfy Row
// Level Security for actions that are not yet tied to any tenant/operator
// (registration, login, password reset) -- it does not expose any
// tenant/operator data, since these queries never touch tenant/operator
// tables.
func (s *Service) systemTx(ctx context.Context) (pgx.Tx, error) {
	tx, err := s.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		return nil, fmt.Errorf("begin system transaction: %w", err)
	}
	return tx, nil
}

func (s *Service) Register(ctx context.Context, email, password string) (User, error) {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return User{}, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if _, exists, err := getUserByEmail(ctx, tx, email); err != nil {
		return User{}, err
	} else if exists {
		return User{}, ErrEmailAlreadyRegistered
	}

	hash, err := s.hasher.Hash(password)
	if err != nil {
		return User{}, fmt.Errorf("hash password: %w", err)
	}

	user, err := createUser(ctx, tx, email, hash)
	if err != nil {
		return User{}, err
	}

	rawToken, tokenHash, err := security.GenerateOpaqueToken(32)
	if err != nil {
		return User{}, err
	}
	if err := insertEmailVerificationToken(ctx, tx, user.ID, tokenHash, s.cfg.EmailVerificationTTL); err != nil {
		return User{}, err
	}

	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &user.ID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.user_registered",
		TargetType:  "user",
		TargetID:    &user.ID,
		Evidence:    map[string]any{"email": user.Email},
	}); err != nil {
		return User{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return User{}, fmt.Errorf("commit registration: %w", err)
	}

	verifyLink := fmt.Sprintf("%s/verify-email?token=%s", s.cfg.PublicBaseURL, rawToken)
	_ = s.mailer.Send(user.Email, "Verify your GRIDKEEP account",
		fmt.Sprintf("Welcome to GRIDKEEP.\n\nVerify your email address:\n%s\n\nThis link expires in %s.", verifyLink, s.cfg.EmailVerificationTTL))

	return user, nil
}

func (s *Service) VerifyEmail(ctx context.Context, rawToken string) error {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	tokenHash := security.HashToken(rawToken)
	userID, ok, err := consumeEmailVerificationToken(ctx, tx, tokenHash)
	if err != nil {
		return err
	}
	if !ok {
		return ErrInvalidToken
	}

	if err := markEmailVerified(ctx, tx, userID); err != nil {
		return err
	}

	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.email_verified",
		TargetType:  "user",
		TargetID:    &userID,
	}); err != nil {
		return err
	}

	return tx.Commit(ctx)
}

type LoginResult struct {
	Session      *AuthenticatedSession
	MFAChallenge string // raw challenge token, set only when MFA is required
}

type AuthenticatedSession struct {
	RawToken  string
	SessionID uuid.UUID
	UserID    uuid.UUID
	ExpiresAt time.Time
}

// nonExistentUserDummyHash is a fixed, valid-format Argon2id hash checked
// against when no user exists for the supplied email, so Verify performs a
// real computation of comparable cost either way, reducing (not fully
// eliminating) the timing/enumeration signal between "no such user" and
// "wrong password".
const nonExistentUserDummyHash = "$argon2id$v=19$m=65536,t=3,p=2$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

// Login verifies credentials and either returns a live session (MFA
// disabled) or an MFA challenge token that must be exchanged via
// VerifyMFAChallenge. Failed and successful attempts are both recorded for
// lockout accounting; a locked-out account is rejected before the password
// is even checked, and the rejection reason given to the client is
// intentionally generic (matches ErrInvalidCredentials) to avoid confirming
// account existence or lockout state to an attacker.
func (s *Service) Login(ctx context.Context, email, password, ip, userAgent string) (LoginResult, error) {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return LoginResult{}, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	failedCount, err := countRecentFailedAttempts(ctx, tx, email, s.cfg.LoginLockoutWindow)
	if err != nil {
		return LoginResult{}, err
	}
	if failedCount >= s.cfg.LoginLockoutThreshold {
		if err := tx.Commit(ctx); err != nil {
			return LoginResult{}, err
		}
		return LoginResult{}, ErrAccountLocked
	}

	user, exists, err := getUserByEmail(ctx, tx, email)
	if err != nil {
		return LoginResult{}, err
	}

	candidateHash := user.PasswordHash
	if !exists {
		candidateHash = nonExistentUserDummyHash
	}
	validPassword, verr := s.hasher.Verify(password, candidateHash)
	if verr != nil {
		validPassword = false
	}

	if !exists || !validPassword {
		if err := recordLoginAttempt(ctx, tx, email, ip, false); err != nil {
			return LoginResult{}, err
		}
		if err := tx.Commit(ctx); err != nil {
			return LoginResult{}, err
		}
		return LoginResult{}, ErrInvalidCredentials
	}

	if user.EmailVerifiedAt == nil {
		if err := tx.Commit(ctx); err != nil {
			return LoginResult{}, err
		}
		return LoginResult{}, ErrEmailNotVerified
	}

	if err := recordLoginAttempt(ctx, tx, email, ip, true); err != nil {
		return LoginResult{}, err
	}

	if user.MFAEnabled {
		rawChallenge, challengeHash, cerr := security.GenerateOpaqueToken(32)
		if cerr != nil {
			return LoginResult{}, cerr
		}
		if err := createMFAChallenge(ctx, tx, user.ID, challengeHash, s.cfg.MFAChallengeTTL); err != nil {
			return LoginResult{}, err
		}
		if err := audit.Record(ctx, tx, audit.Event{
			ActorUserID: &user.ID,
			ScopeType:   audit.ScopePlatform,
			Action:      "identity.login_mfa_challenge_issued",
			TargetType:  "user",
			TargetID:    &user.ID,
		}); err != nil {
			return LoginResult{}, err
		}
		if err := tx.Commit(ctx); err != nil {
			return LoginResult{}, err
		}
		return LoginResult{MFAChallenge: rawChallenge}, nil
	}

	session, err := s.createSessionForUser(ctx, tx, user.ID, ip, userAgent)
	if err != nil {
		return LoginResult{}, err
	}

	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &user.ID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.login_succeeded",
		TargetType:  "user",
		TargetID:    &user.ID,
	}); err != nil {
		return LoginResult{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return LoginResult{}, err
	}

	return LoginResult{Session: session}, nil
}

func (s *Service) VerifyMFAChallenge(ctx context.Context, rawChallenge, code, ip, userAgent string) (*AuthenticatedSession, error) {
	challengeHash := security.HashToken(rawChallenge)

	// Step 1: durably record this attempt against the challenge's fixed
	// attempt budget, in its own transaction committed before the code is
	// checked. This must happen first and must survive independent of
	// whether the code turns out to be valid -- otherwise an invalid code
	// (or any later error) rolls back the attempt along with everything
	// else in that transaction, letting the same challenge be retried
	// without limit. See migration 0010 and incrementMFAChallengeAttempt.
	attemptTx, err := s.systemTx(ctx)
	if err != nil {
		return nil, err
	}
	userID, ok, err := incrementMFAChallengeAttempt(ctx, attemptTx, challengeHash, s.cfg.MFAMaxAttempts)
	if err != nil {
		_ = attemptTx.Rollback(ctx)
		return nil, err
	}
	if !ok {
		_ = attemptTx.Rollback(ctx)
		return nil, ErrInvalidToken
	}
	if err := attemptTx.Commit(ctx); err != nil {
		return nil, err
	}

	// Step 2: validate the code and, only on success, consume the
	// challenge and create the session. A failed validation here never
	// re-opens the challenge -- the attempt was already spent above.
	tx, err := s.systemTx(ctx)
	if err != nil {
		return nil, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	lockedUserID, stillOpen, err := consumeMFAChallengeIfUnused(ctx, tx, challengeHash)
	if err != nil {
		return nil, err
	}
	if !stillOpen || lockedUserID != userID {
		return nil, ErrInvalidToken
	}

	encSecret, ok, err := getMFASecret(ctx, tx, userID)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, ErrMFANotEnrolled
	}

	valid, err := s.totp.Validate(code, encSecret)
	if err != nil {
		return nil, fmt.Errorf("validate totp: %w", err)
	}
	if !valid {
		// Feed the failed guess into the same account-level lockout that
		// protects the password step, so brute-forcing across many
		// freshly-minted challenges eventually locks the account instead
		// of resetting the attacker's budget on every new challenge.
		if user, exists, uerr := getUserByID(ctx, tx, userID); uerr == nil && exists {
			_ = recordLoginAttempt(ctx, tx, user.Email, ip, false)
		}
		if err := tx.Commit(ctx); err != nil {
			return nil, err
		}
		return nil, ErrInvalidMFACode
	}

	if err := markMFAChallengeConsumed(ctx, tx, challengeHash); err != nil {
		return nil, err
	}

	session, err := s.createSessionForUser(ctx, tx, userID, ip, userAgent)
	if err != nil {
		return nil, err
	}

	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.login_mfa_verified",
		TargetType:  "user",
		TargetID:    &userID,
	}); err != nil {
		return nil, err
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, err
	}
	return session, nil
}

func (s *Service) createSessionForUser(ctx context.Context, c conn, userID uuid.UUID, ip, userAgent string) (*AuthenticatedSession, error) {
	rawToken, tokenHash, err := security.GenerateOpaqueToken(32)
	if err != nil {
		return nil, err
	}
	sessionID, err := createSession(ctx, c, userID, tokenHash, ip, userAgent, s.cfg.SessionTTL)
	if err != nil {
		return nil, err
	}
	return &AuthenticatedSession{
		RawToken:  rawToken,
		SessionID: sessionID,
		UserID:    userID,
		ExpiresAt: time.Now().Add(s.cfg.SessionTTL),
	}, nil
}

func (s *Service) Logout(ctx context.Context, sessionID uuid.UUID) error {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if err := revokeSession(ctx, tx, sessionID); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

type AuthResult struct {
	UserID    uuid.UUID
	SessionID uuid.UUID
	StepUpAt  *time.Time
}

// ValidateSession implements httpserver.SessionValidator. It is on the hot
// path of every authenticated request, so it runs directly against the pool
// without opening a scoped transaction (sessions carry no tenant/operator
// ownership and no RLS is defined on the sessions table).
func (s *Service) ValidateSession(ctx context.Context, rawToken string) (AuthResult, error) {
	tokenHash := security.HashToken(rawToken)
	session, ok, err := getSessionByTokenHash(ctx, s.store.Pool, tokenHash)
	if err != nil {
		return AuthResult{}, err
	}
	if !ok || session.RevokedAt != nil || time.Now().After(session.ExpiresAt) {
		return AuthResult{}, ErrInvalidToken
	}
	_ = touchSession(ctx, s.store.Pool, session.ID)
	return AuthResult{UserID: session.UserID, SessionID: session.ID, StepUpAt: session.StepUpAt}, nil
}

// RequestPasswordReset always returns nil (success) regardless of whether
// the email exists, to avoid confirming account existence. It only emails a
// reset link when the account is real.
func (s *Service) RequestPasswordReset(ctx context.Context, email string) error {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	user, exists, err := getUserByEmail(ctx, tx, email)
	if err != nil {
		return err
	}
	if !exists {
		return tx.Commit(ctx)
	}

	rawToken, tokenHash, err := security.GenerateOpaqueToken(32)
	if err != nil {
		return err
	}
	if err := insertPasswordResetToken(ctx, tx, user.ID, tokenHash, s.cfg.PasswordResetTTL); err != nil {
		return err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &user.ID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.password_reset_requested",
		TargetType:  "user",
		TargetID:    &user.ID,
	}); err != nil {
		return err
	}
	if err := tx.Commit(ctx); err != nil {
		return err
	}

	resetLink := fmt.Sprintf("%s/reset-password?token=%s", s.cfg.PublicBaseURL, rawToken)
	_ = s.mailer.Send(user.Email, "Reset your GRIDKEEP password",
		fmt.Sprintf("Reset your password:\n%s\n\nThis link expires in %s. If you did not request this, ignore this email.", resetLink, s.cfg.PasswordResetTTL))

	return nil
}

func (s *Service) ResetPassword(ctx context.Context, rawToken, newPassword string) error {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	tokenHash := security.HashToken(rawToken)
	userID, ok, err := consumePasswordResetToken(ctx, tx, tokenHash)
	if err != nil {
		return err
	}
	if !ok {
		return ErrInvalidToken
	}

	hash, err := s.hasher.Hash(newPassword)
	if err != nil {
		return err
	}
	if err := updatePasswordHash(ctx, tx, userID, hash); err != nil {
		return err
	}
	// Resetting a password invalidates every existing session -- a stolen
	// session token must not survive a credential reset.
	if err := revokeAllUserSessions(ctx, tx, userID); err != nil {
		return err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.password_reset_completed",
		TargetType:  "user",
		TargetID:    &userID,
	}); err != nil {
		return err
	}

	return tx.Commit(ctx)
}

// ChangePassword requires the caller to present their current password
// (proof of possession) even though they already hold a valid session -- a
// stolen session cookie alone is not sufficient to change credentials.
func (s *Service) ChangePassword(ctx context.Context, userID uuid.UUID, currentPassword, newPassword string) error {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	user, exists, err := getUserByID(ctx, tx, userID)
	if err != nil {
		return err
	}
	if !exists {
		return ErrInvalidCredentials
	}
	valid, err := s.hasher.Verify(currentPassword, user.PasswordHash)
	if err != nil || !valid {
		return ErrInvalidCredentials
	}

	hash, err := s.hasher.Hash(newPassword)
	if err != nil {
		return err
	}
	if err := updatePasswordHash(ctx, tx, userID, hash); err != nil {
		return err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.password_changed",
		TargetType:  "user",
		TargetID:    &userID,
	}); err != nil {
		return err
	}

	return tx.Commit(ctx)
}

func (s *Service) StepUp(ctx context.Context, sessionID, userID uuid.UUID, password string) error {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	user, exists, err := getUserByID(ctx, tx, userID)
	if err != nil {
		return err
	}
	if !exists {
		return ErrInvalidCredentials
	}
	valid, err := s.hasher.Verify(password, user.PasswordHash)
	if err != nil || !valid {
		return ErrInvalidCredentials
	}
	if err := markSessionStepUp(ctx, tx, sessionID); err != nil {
		return err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.step_up_authenticated",
		TargetType:  "session",
	}); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

func (s *Service) EnrollMFA(ctx context.Context, userID uuid.UUID) (otpauthURI string, err error) {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return "", err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	user, exists, err := getUserByID(ctx, tx, userID)
	if err != nil {
		return "", err
	}
	if !exists {
		return "", ErrInvalidCredentials
	}
	if user.MFAEnabled {
		return "", ErrMFAAlreadyEnabled
	}

	uri, encSecret, err := s.totp.GenerateSecret(user.Email)
	if err != nil {
		return "", err
	}
	if err := upsertMFASecret(ctx, tx, userID, encSecret); err != nil {
		return "", err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.mfa_enrollment_started",
		TargetType:  "user",
		TargetID:    &userID,
	}); err != nil {
		return "", err
	}
	if err := tx.Commit(ctx); err != nil {
		return "", err
	}
	return uri, nil
}

func (s *Service) ConfirmMFA(ctx context.Context, userID uuid.UUID, code string) error {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	encSecret, ok, err := getMFASecret(ctx, tx, userID)
	if err != nil {
		return err
	}
	if !ok {
		return ErrMFANotEnrolled
	}
	valid, err := s.totp.Validate(code, encSecret)
	if err != nil {
		return err
	}
	if !valid {
		return ErrInvalidMFACode
	}

	if err := confirmMFASecret(ctx, tx, userID); err != nil {
		return err
	}
	if err := setMFAEnabled(ctx, tx, userID, true); err != nil {
		return err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.mfa_enabled",
		TargetType:  "user",
		TargetID:    &userID,
	}); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

func (s *Service) DisableMFA(ctx context.Context, userID uuid.UUID, code string) error {
	tx, err := s.systemTx(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	encSecret, ok, err := getMFASecret(ctx, tx, userID)
	if err != nil {
		return err
	}
	if !ok {
		return ErrMFANotEnrolled
	}
	valid, err := s.totp.Validate(code, encSecret)
	if err != nil {
		return err
	}
	if !valid {
		return ErrInvalidMFACode
	}

	if err := deleteMFASecret(ctx, tx, userID); err != nil {
		return err
	}
	if err := setMFAEnabled(ctx, tx, userID, false); err != nil {
		return err
	}
	if err := audit.Record(ctx, tx, audit.Event{
		ActorUserID: &userID,
		ScopeType:   audit.ScopePlatform,
		Action:      "identity.mfa_disabled",
		TargetType:  "user",
		TargetID:    &userID,
	}); err != nil {
		return err
	}
	return tx.Commit(ctx)
}
