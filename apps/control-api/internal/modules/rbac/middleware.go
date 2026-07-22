package rbac

import (
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gridkeep/control-api/internal/platform/apierror"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
)

type Middleware struct {
	store  *dbpkg.Store
	logger *slog.Logger
}

func NewMiddleware(store *dbpkg.Store, logger *slog.Logger) *Middleware {
	return &Middleware{store: store, logger: logger}
}

// RequireEnterprisePermission authorizes a request scoped to the
// {tenantID} chi URL parameter. It implements the enterprise-scope slice of
// the platform's mandatory authorization pipeline: authenticated identity,
// active session (already established by httpserver middleware), active
// membership, tenant active status, and role -> permission grant. A user
// with no membership is still admitted if they hold an active, approved,
// non-expired support-access grant for that tenant (platform support path),
// which is separately audited.
func (m *Middleware) RequireEnterprisePermission(permissionKey string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := r.Context()
			authUser, ok := httpserver.AuthUser(ctx)
			if !ok {
				apierror.WriteJSON(w, r, m.logger, apierror.ErrUnauthenticated)
				return
			}

			tenantID, err := uuid.Parse(chi.URLParam(r, "tenantID"))
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.WithField(apierror.ErrValidation, "tenantID", "must be a valid UUID"))
				return
			}

			tx, err := m.store.BeginScoped(ctx, dbpkg.Scope{TenantID: &tenantID})
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to open scoped transaction", err))
				return
			}
			scopedTx := &ScopedTx{Tx: tx}
			defer func() {
				if !scopedTx.committed {
					_ = tx.Rollback(ctx)
				}
			}()

			roleKey, tenantStatus, granted, err := enterpriseMembershipPermission(ctx, tx, authUser.UserID, tenantID, permissionKey)
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", err))
				return
			}

			viaSupportGrant := false
			if !granted {
				// No membership at all -- check for a JIT support-access grant.
				hasGrant, gerr := activeSupportAccessGrant(ctx, m.store.Pool, authUser.UserID, "enterprise", tenantID)
				if gerr != nil {
					apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", gerr))
					return
				}
				if !hasGrant {
					apierror.WriteJSON(w, r, m.logger, apierror.ErrForbidden)
					return
				}
				// Support access bypasses tenant-status/permission checks
				// deliberately: it exists for support engineers to act during
				// incidents even on a suspended tenant, strictly time-boxed
				// and pre-approved.
				viaSupportGrant = true
				roleKey = "support_access_grant"
			} else if tenantStatus != "active" {
				apierror.WriteJSON(w, r, m.logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, "This enterprise tenant is not active."))
				return
			}

			scope := Scope{Type: ScopeEnterprise, TenantID: &tenantID, RoleKey: roleKey, ViaSupportGrant: viaSupportGrant}
			ctx = withScope(ctx, scope)
			ctx = withTx(ctx, scopedTx)

			if viaSupportGrant {
				if aerr := audit.Record(ctx, tx, audit.Event{
					ActorUserID: &authUser.UserID,
					ScopeType:   audit.ScopeEnterprise,
					ScopeID:     &tenantID,
					Action:      "support_access.request_served",
					TargetType:  "http_request",
					Evidence:    map[string]any{"path": r.URL.Path, "method": r.Method, "permission": permissionKey},
				}); aerr != nil {
					apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "audit logging failed", aerr))
					return
				}
			}

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// RequireEnterpriseMembership authorizes any active member of the
// {tenantID} tenant, without checking a specific permission. Used for
// read views that every member may see (tenant profile, member roster).
// Support-access grants are honored the same way as RequireEnterprisePermission.
func (m *Middleware) RequireEnterpriseMembership() func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := r.Context()
			authUser, ok := httpserver.AuthUser(ctx)
			if !ok {
				apierror.WriteJSON(w, r, m.logger, apierror.ErrUnauthenticated)
				return
			}
			tenantID, err := uuid.Parse(chi.URLParam(r, "tenantID"))
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.WithField(apierror.ErrValidation, "tenantID", "must be a valid UUID"))
				return
			}
			tx, err := m.store.BeginScoped(ctx, dbpkg.Scope{TenantID: &tenantID})
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to open scoped transaction", err))
				return
			}
			scopedTx := &ScopedTx{Tx: tx}
			defer func() {
				if !scopedTx.committed {
					_ = tx.Rollback(ctx)
				}
			}()

			roleKey, _, isMember, err := enterpriseMembership(ctx, tx, authUser.UserID, tenantID)
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", err))
				return
			}
			viaSupportGrant := false
			if !isMember {
				hasGrant, gerr := activeSupportAccessGrant(ctx, m.store.Pool, authUser.UserID, "enterprise", tenantID)
				if gerr != nil {
					apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", gerr))
					return
				}
				if !hasGrant {
					apierror.WriteJSON(w, r, m.logger, apierror.ErrForbidden)
					return
				}
				viaSupportGrant = true
				roleKey = "support_access_grant"
			}

			ctx = withScope(ctx, Scope{Type: ScopeEnterprise, TenantID: &tenantID, RoleKey: roleKey, ViaSupportGrant: viaSupportGrant})
			ctx = withTx(ctx, scopedTx)

			if viaSupportGrant {
				if aerr := audit.Record(ctx, tx, audit.Event{
					ActorUserID: &authUser.UserID,
					ScopeType:   audit.ScopeEnterprise,
					ScopeID:     &tenantID,
					Action:      "support_access.request_served",
					TargetType:  "http_request",
					Evidence:    map[string]any{"path": r.URL.Path, "method": r.Method},
				}); aerr != nil {
					apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "audit logging failed", aerr))
					return
				}
			}

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// RequireOperatorMembership is the operator-scope equivalent of RequireEnterpriseMembership.
func (m *Middleware) RequireOperatorMembership() func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := r.Context()
			authUser, ok := httpserver.AuthUser(ctx)
			if !ok {
				apierror.WriteJSON(w, r, m.logger, apierror.ErrUnauthenticated)
				return
			}
			operatorID, err := uuid.Parse(chi.URLParam(r, "operatorID"))
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.WithField(apierror.ErrValidation, "operatorID", "must be a valid UUID"))
				return
			}
			tx, err := m.store.BeginScoped(ctx, dbpkg.Scope{OperatorID: &operatorID})
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to open scoped transaction", err))
				return
			}
			scopedTx := &ScopedTx{Tx: tx}
			defer func() {
				if !scopedTx.committed {
					_ = tx.Rollback(ctx)
				}
			}()

			roleKey, _, isMember, err := operatorMembership(ctx, tx, authUser.UserID, operatorID)
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", err))
				return
			}
			viaSupportGrant := false
			if !isMember {
				hasGrant, gerr := activeSupportAccessGrant(ctx, m.store.Pool, authUser.UserID, "operator", operatorID)
				if gerr != nil {
					apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", gerr))
					return
				}
				if !hasGrant {
					apierror.WriteJSON(w, r, m.logger, apierror.ErrForbidden)
					return
				}
				viaSupportGrant = true
				roleKey = "support_access_grant"
			}

			ctx = withScope(ctx, Scope{Type: ScopeOperator, OperatorID: &operatorID, RoleKey: roleKey, ViaSupportGrant: viaSupportGrant})
			ctx = withTx(ctx, scopedTx)

			if viaSupportGrant {
				if aerr := audit.Record(ctx, tx, audit.Event{
					ActorUserID: &authUser.UserID,
					ScopeType:   audit.ScopeOperator,
					ScopeID:     &operatorID,
					Action:      "support_access.request_served",
					TargetType:  "http_request",
					Evidence:    map[string]any{"path": r.URL.Path, "method": r.Method},
				}); aerr != nil {
					apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "audit logging failed", aerr))
					return
				}
			}

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// RequireOperatorPermission is the operator-scope equivalent of
// RequireEnterprisePermission, keyed on the {operatorID} chi URL parameter.
func (m *Middleware) RequireOperatorPermission(permissionKey string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := r.Context()
			authUser, ok := httpserver.AuthUser(ctx)
			if !ok {
				apierror.WriteJSON(w, r, m.logger, apierror.ErrUnauthenticated)
				return
			}

			operatorID, err := uuid.Parse(chi.URLParam(r, "operatorID"))
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.WithField(apierror.ErrValidation, "operatorID", "must be a valid UUID"))
				return
			}

			tx, err := m.store.BeginScoped(ctx, dbpkg.Scope{OperatorID: &operatorID})
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to open scoped transaction", err))
				return
			}
			scopedTx := &ScopedTx{Tx: tx}
			defer func() {
				if !scopedTx.committed {
					_ = tx.Rollback(ctx)
				}
			}()

			roleKey, operatorStatus, granted, err := operatorMembershipPermission(ctx, tx, authUser.UserID, operatorID, permissionKey)
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", err))
				return
			}

			viaSupportGrant := false
			if !granted {
				hasGrant, gerr := activeSupportAccessGrant(ctx, m.store.Pool, authUser.UserID, "operator", operatorID)
				if gerr != nil {
					apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", gerr))
					return
				}
				if !hasGrant {
					apierror.WriteJSON(w, r, m.logger, apierror.ErrForbidden)
					return
				}
				viaSupportGrant = true
				roleKey = "support_access_grant"
			} else if operatorStatus != "active" && operatorStatus != "approved" {
				apierror.WriteJSON(w, r, m.logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, "This operator account is not active."))
				return
			}

			scope := Scope{Type: ScopeOperator, OperatorID: &operatorID, RoleKey: roleKey, ViaSupportGrant: viaSupportGrant}
			ctx = withScope(ctx, scope)
			ctx = withTx(ctx, scopedTx)

			if viaSupportGrant {
				if aerr := audit.Record(ctx, tx, audit.Event{
					ActorUserID: &authUser.UserID,
					ScopeType:   audit.ScopeOperator,
					ScopeID:     &operatorID,
					Action:      "support_access.request_served",
					TargetType:  "http_request",
					Evidence:    map[string]any{"path": r.URL.Path, "method": r.Method, "permission": permissionKey},
				}); aerr != nil {
					apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "audit logging failed", aerr))
					return
				}
			}

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// RequirePlatformPermission authorizes a request against the caller's
// platform_role_assignments. Platform roles are never inherited from
// enterprise/operator memberships and grant no enterprise/operator scope by
// themselves -- accessing a specific tenant/operator's data still requires
// a support-access grant (see RequireEnterprisePermission/RequireOperatorPermission).
func (m *Middleware) RequirePlatformPermission(permissionKey string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := r.Context()
			authUser, ok := httpserver.AuthUser(ctx)
			if !ok {
				apierror.WriteJSON(w, r, m.logger, apierror.ErrUnauthenticated)
				return
			}

			roleKey, granted, err := platformPermission(ctx, m.store.Pool, authUser.UserID, permissionKey)
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "authorization check failed", err))
				return
			}
			if !granted {
				apierror.WriteJSON(w, r, m.logger, apierror.ErrForbidden)
				return
			}

			tx, err := m.store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
			if err != nil {
				apierror.WriteJSON(w, r, m.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to open scoped transaction", err))
				return
			}
			scopedTx := &ScopedTx{Tx: tx}
			defer func() {
				if !scopedTx.committed {
					_ = tx.Rollback(ctx)
				}
			}()

			scope := Scope{Type: ScopePlatform, PlatformBypass: true, RoleKey: roleKey}
			ctx = withScope(ctx, scope)
			ctx = withTx(ctx, scopedTx)

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}
