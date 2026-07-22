package identity

import (
	"context"

	"gridkeep/control-api/internal/platform/httpserver"
)

// SessionValidatorAdapter satisfies httpserver.SessionValidator without the
// platform HTTP layer importing the identity module directly.
type SessionValidatorAdapter struct {
	Service *Service
}

func (a SessionValidatorAdapter) ValidateSession(ctx context.Context, rawSessionToken string) (httpserver.AuthenticatedUser, error) {
	result, err := a.Service.ValidateSession(ctx, rawSessionToken)
	if err != nil {
		return httpserver.AuthenticatedUser{}, err
	}
	return httpserver.AuthenticatedUser{
		UserID:       result.UserID,
		SessionID:    result.SessionID,
		StepUpAt:     result.StepUpAt,
		MFASatisfied: true,
	}, nil
}
