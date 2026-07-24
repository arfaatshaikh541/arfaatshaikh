package identity

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"gridkeep/control-api/internal/platform/apierror"
	"gridkeep/control-api/internal/platform/httpserver"
)

type Handlers struct {
	svc          *Service
	logger       *slog.Logger
	cookieName   string
	cookieSecure bool
}

func NewHandlers(svc *Service, logger *slog.Logger, cookieName string, cookieSecure bool) *Handlers {
	return &Handlers{svc: svc, logger: logger, cookieName: cookieName, cookieSecure: cookieSecure}
}

func decodeJSON(r *http.Request, dst any) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	return dec.Decode(dst)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func clientIP(r *http.Request) string {
	if idx := strings.LastIndex(r.RemoteAddr, ":"); idx != -1 {
		return r.RemoteAddr[:idx]
	}
	return r.RemoteAddr
}

func (h *Handlers) setSessionCookie(w http.ResponseWriter, rawToken string, expiresAt time.Time) {
	http.SetCookie(w, &http.Cookie{
		Name:     h.cookieName,
		Value:    rawToken,
		Path:     "/",
		HttpOnly: true,
		Secure:   h.cookieSecure,
		SameSite: http.SameSiteLaxMode,
		Expires:  expiresAt,
	})
}

func (h *Handlers) clearSessionCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:     h.cookieName,
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		Secure:   h.cookieSecure,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   -1,
	})
}

type registerRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

func (h *Handlers) Register(w http.ResponseWriter, r *http.Request) {
	var req registerRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if !validEmail(req.Email) {
		apierror.WriteJSON(w, r, h.logger, apierror.WithField(apierror.ErrValidation, "email", "must be a valid email address"))
		return
	}
	if len(req.Password) < 12 {
		apierror.WriteJSON(w, r, h.logger, apierror.WithField(apierror.ErrValidation, "password", "must be at least 12 characters"))
		return
	}

	user, err := h.svc.Register(r.Context(), req.Email, req.Password)
	if err != nil {
		if errors.Is(err, ErrEmailAlreadyRegistered) {
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusConflict, apierror.CodeConflict, "An account with this email already exists."))
			return
		}
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "registration failed", err))
		return
	}

	writeJSON(w, http.StatusCreated, map[string]any{
		"id":    user.ID,
		"email": user.Email,
	})
}

type verifyEmailRequest struct {
	Token string `json:"token"`
}

func (h *Handlers) VerifyEmail(w http.ResponseWriter, r *http.Request) {
	var req verifyEmailRequest
	if err := decodeJSON(r, &req); err != nil || req.Token == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.VerifyEmail(r.Context(), req.Token); err != nil {
		if errors.Is(err, ErrInvalidToken) {
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, "This verification link is invalid or has expired."))
			return
		}
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "email verification failed", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "verified"})
}

type loginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

func (h *Handlers) Login(w http.ResponseWriter, r *http.Request) {
	var req loginRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}

	result, err := h.svc.Login(r.Context(), req.Email, req.Password, clientIP(r), r.UserAgent())
	if err != nil {
		switch {
		case errors.Is(err, ErrInvalidCredentials):
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "Invalid email or password."))
		case errors.Is(err, ErrAccountLocked):
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusTooManyRequests, apierror.CodeRateLimited, "Too many failed attempts. Try again later."))
		case errors.Is(err, ErrEmailNotVerified):
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, "Please verify your email address before logging in."))
		default:
			apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "login failed", err))
		}
		return
	}

	if result.MFAChallenge != "" {
		writeJSON(w, http.StatusOK, map[string]any{"mfa_required": true, "mfa_challenge": result.MFAChallenge})
		return
	}

	h.setSessionCookie(w, result.Session.RawToken, result.Session.ExpiresAt)
	writeJSON(w, http.StatusOK, map[string]any{"mfa_required": false})
}

type mfaVerifyRequest struct {
	Challenge string `json:"mfa_challenge"`
	Code      string `json:"code"`
}

func (h *Handlers) VerifyMFA(w http.ResponseWriter, r *http.Request) {
	var req mfaVerifyRequest
	if err := decodeJSON(r, &req); err != nil || req.Challenge == "" || req.Code == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	session, err := h.svc.VerifyMFAChallenge(r.Context(), req.Challenge, req.Code, clientIP(r), r.UserAgent())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "Invalid or expired MFA challenge."))
		return
	}
	h.setSessionCookie(w, session.RawToken, session.ExpiresAt)
	writeJSON(w, http.StatusOK, map[string]any{"status": "authenticated"})
}

func (h *Handlers) Logout(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if ok {
		_ = h.svc.Logout(r.Context(), authUser.SessionID)
	}
	h.clearSessionCookie(w)
	writeJSON(w, http.StatusOK, map[string]any{"status": "logged_out"})
}

func (h *Handlers) Me(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	platformRoles, err := h.svc.MyPlatformRoleKeys(r.Context(), authUser.UserID)
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to load platform roles", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"user_id":        authUser.UserID,
		"platform_roles": platformRoles,
	})
}

type requestPasswordResetRequest struct {
	Email string `json:"email"`
}

func (h *Handlers) RequestPasswordReset(w http.ResponseWriter, r *http.Request) {
	var req requestPasswordResetRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.RequestPasswordReset(r.Context(), req.Email); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "password reset request failed", err))
		return
	}
	// Always identical response, whether or not the email exists.
	writeJSON(w, http.StatusOK, map[string]any{"status": "if_account_exists_email_sent"})
}

type resetPasswordRequest struct {
	Token       string `json:"token"`
	NewPassword string `json:"new_password"`
}

func (h *Handlers) ResetPassword(w http.ResponseWriter, r *http.Request) {
	var req resetPasswordRequest
	if err := decodeJSON(r, &req); err != nil || req.Token == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if len(req.NewPassword) < 12 {
		apierror.WriteJSON(w, r, h.logger, apierror.WithField(apierror.ErrValidation, "new_password", "must be at least 12 characters"))
		return
	}
	if err := h.svc.ResetPassword(r.Context(), req.Token, req.NewPassword); err != nil {
		if errors.Is(err, ErrInvalidToken) {
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, "This reset link is invalid or has expired."))
			return
		}
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "password reset failed", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "password_reset"})
}

type changePasswordRequest struct {
	CurrentPassword string `json:"current_password"`
	NewPassword     string `json:"new_password"`
}

func (h *Handlers) ChangePassword(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	var req changePasswordRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if len(req.NewPassword) < 12 {
		apierror.WriteJSON(w, r, h.logger, apierror.WithField(apierror.ErrValidation, "new_password", "must be at least 12 characters"))
		return
	}
	if err := h.svc.ChangePassword(r.Context(), authUser.UserID, req.CurrentPassword, req.NewPassword); err != nil {
		if errors.Is(err, ErrInvalidCredentials) {
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "Current password is incorrect."))
			return
		}
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "password change failed", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "password_changed"})
}

type stepUpRequest struct {
	Password string `json:"password"`
}

func (h *Handlers) StepUp(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	var req stepUpRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.StepUp(r.Context(), authUser.SessionID, authUser.UserID, req.Password); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusUnauthorized, apierror.CodeUnauthenticated, "Re-authentication failed."))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "step_up_complete"})
}

func (h *Handlers) EnrollMFA(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	uri, err := h.svc.EnrollMFA(r.Context(), authUser.UserID)
	if err != nil {
		if errors.Is(err, ErrMFAAlreadyEnabled) {
			apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusConflict, apierror.CodeConflict, "MFA is already enabled."))
			return
		}
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "mfa enrollment failed", err))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"otpauth_uri": uri})
}

type mfaCodeRequest struct {
	Code string `json:"code"`
}

func (h *Handlers) ConfirmMFA(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	var req mfaCodeRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.ConfirmMFA(r.Context(), authUser.UserID, req.Code); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, "Invalid MFA code."))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "mfa_enabled"})
}

func (h *Handlers) DisableMFA(w http.ResponseWriter, r *http.Request) {
	authUser, ok := httpserver.AuthUser(r.Context())
	if !ok {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrUnauthenticated)
		return
	}
	var req mfaCodeRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	if err := h.svc.DisableMFA(r.Context(), authUser.UserID, req.Code); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, "Invalid MFA code."))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "mfa_disabled"})
}

func validEmail(email string) bool {
	at := strings.IndexByte(email, '@')
	return at > 0 && at < len(email)-1 && !strings.ContainsAny(email, " \t\n")
}
