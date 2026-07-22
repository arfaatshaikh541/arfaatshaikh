package rbac

import "github.com/google/uuid"

type ScopeType string

const (
	ScopeEnterprise ScopeType = "enterprise"
	ScopeOperator   ScopeType = "operator"
	ScopePlatform   ScopeType = "platform"
)

// Scope is the server-resolved identity a request is authorized to act as.
// It is produced exclusively by the middleware in this package from the
// authenticated session's memberships — never from client-supplied path or
// body parameters.
type Scope struct {
	Type            ScopeType
	TenantID        *uuid.UUID
	OperatorID      *uuid.UUID
	PlatformBypass  bool
	RoleKey         string
	ViaSupportGrant bool
}

type Role struct {
	ID          uuid.UUID
	ScopeType   string
	Key         string
	Name        string
	Description string
}

type Permission struct {
	ID        uuid.UUID
	Key       string
	ScopeType string
}
