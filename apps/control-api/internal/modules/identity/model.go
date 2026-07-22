package identity

import (
	"time"

	"github.com/google/uuid"
)

type User struct {
	ID              uuid.UUID
	Email           string
	PasswordHash    string
	EmailVerifiedAt *time.Time
	Status          string
	MFAEnabled      bool
	CreatedAt       time.Time
}

type Session struct {
	ID        uuid.UUID
	UserID    uuid.UUID
	ExpiresAt time.Time
	RevokedAt *time.Time
	StepUpAt  *time.Time
}
