# Organisation RBAC

Permissions are global vocabulary records. Roles belong to exactly one organisation and map to permissions through `role_permissions`. Memberships bind a user to one organisation and one role.

Organisation creation atomically creates system Owner and Member roles, assigns the owner membership, and emits an audit event. Permission checks occur in FastAPI dependencies before route logic. The browser is never authoritative for tenant or role selection.
