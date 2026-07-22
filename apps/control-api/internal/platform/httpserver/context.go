package httpserver

import (
	"context"
	"time"

	"github.com/google/uuid"
)

type ctxKey int

const (
	ctxKeyAuthUser ctxKey = iota
)

// AuthenticatedUser is the identity resolved from a valid session cookie.
// It is the ONLY source of truth for "who is making this request" — no
// handler may trust a client-supplied user/tenant/operator identifier
// instead of this value.
type AuthenticatedUser struct {
	UserID       uuid.UUID
	SessionID    uuid.UUID
	StepUpAt     *time.Time
	MFASatisfied bool
}

func withAuthUser(ctx context.Context, u AuthenticatedUser) context.Context {
	return context.WithValue(ctx, ctxKeyAuthUser, u)
}

// AuthUser returns the authenticated user for this request, if any.
func AuthUser(ctx context.Context) (AuthenticatedUser, bool) {
	u, ok := ctx.Value(ctxKeyAuthUser).(AuthenticatedUser)
	return u, ok
}
