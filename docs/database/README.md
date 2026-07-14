# Database — Milestone 1 schema

PostgreSQL 16. UUID primary keys throughout. All timestamps stored as
`timestamptz` (UTC). Every tenant-owned table has row-level security
enabled — see `app/alembic/versions/57bf2768a62d_row_level_security_policies.py`
for the exact policies and the reasoning behind each one.

## Entity-relationship diagram (as built)

```mermaid
erDiagram
    TENANTS ||--o{ TENANT_SETTINGS : has
    TENANTS ||--o{ TENANT_DOMAINS : has
    TENANTS ||--o{ MEMBERSHIPS : has
    TENANTS ||--o{ ROLES : "scopes (nullable = system template)"
    TENANTS ||--o{ INVITATIONS : issues
    TENANTS ||--o{ TENANT_SUBSCRIPTIONS : has
    TENANTS ||--o{ TENANT_FEATURE_OVERRIDES : has
    TENANTS ||--o{ TENANT_ADD_ONS : has
    TENANTS ||--o{ USAGE_RECORDS : accrues
    TENANTS ||--o{ AUDIT_LOGS : scopes
    TENANTS ||--o{ SUPPORT_ACCESS_LOGS : scopes
    TENANTS ||--o{ FEATURE_CHANGE_LOGS : scopes

    USERS ||--o{ MEMBERSHIPS : holds
    USERS ||--o{ SESSIONS : authenticates
    USERS ||--o{ EMAIL_VERIFICATION_TOKENS : requests
    USERS ||--o{ PASSWORD_RESET_TOKENS : requests

    MEMBERSHIPS }o--|| ROLES : "assigned"
    ROLES ||--o{ ROLE_PERMISSIONS : grants
    ROLE_PERMISSIONS }o--|| PERMISSIONS : references
    INVITATIONS }o--|| ROLES : "grants on accept"

    SUBSCRIPTION_PLANS ||--o{ PLAN_FEATURES : includes
    PLAN_FEATURES }o--|| FEATURES : references
    FEATURES }o--|| MODULES : "belongs to"
    TENANT_SUBSCRIPTIONS }o--|| SUBSCRIPTION_PLANS : subscribes
    TENANT_FEATURE_OVERRIDES }o--|| FEATURES : overrides
    ADD_ONS ||--o{ TENANT_ADD_ONS : purchased
    USAGE_METRICS ||--o{ USAGE_RECORDS : tracked

    TENANTS {
        uuid id PK
        string name
        string slug UK
        enum status "ACTIVE|SUSPENDED|READ_ONLY|ARCHIVED"
        timestamptz created_at
        timestamptz updated_at
    }
    TENANT_SETTINGS {
        uuid id PK
        uuid tenant_id FK
        string timezone "default Asia/Dubai"
        string currency "default AED"
        jsonb branding
        jsonb business_hours
    }
    TENANT_DOMAINS {
        uuid id PK
        uuid tenant_id FK
        string domain UK
        bool is_primary
    }
    USERS {
        uuid id PK
        citext email UK
        string password_hash "Argon2id"
        string first_name
        string last_name
        bool email_verified
        bool is_platform_admin
        bool is_active
    }
    MEMBERSHIPS {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        uuid role_id FK
        enum status "ACTIVE|INVITED|SUSPENDED"
    }
    ROLES {
        uuid id PK
        uuid tenant_id FK "nullable = system template"
        string name
        bool is_system
    }
    PERMISSIONS {
        uuid id PK
        string code UK
        string description
        bool is_platform_permission
    }
    ROLE_PERMISSIONS {
        uuid role_id PK,FK
        uuid permission_id PK,FK
    }
    INVITATIONS {
        uuid id PK
        uuid tenant_id FK
        citext email
        uuid role_id FK
        string token_hash UK
        uuid invited_by FK
        timestamptz expires_at
        timestamptz accepted_at
        timestamptz revoked_at
    }
    SESSIONS {
        uuid id PK
        uuid user_id FK
        string session_token_hash UK
        uuid active_tenant_id FK
        string ip_address
        string user_agent
        timestamptz expires_at
        timestamptz revoked_at
    }
    EMAIL_VERIFICATION_TOKENS {
        uuid id PK
        uuid user_id FK
        string token_hash UK
        timestamptz expires_at
        timestamptz used_at
    }
    PASSWORD_RESET_TOKENS {
        uuid id PK
        uuid user_id FK
        string token_hash UK
        timestamptz expires_at
        timestamptz used_at
    }
    LOGIN_ATTEMPTS {
        uuid id PK
        citext email
        string ip_address
        bool success
        timestamptz created_at
    }
    MODULES {
        uuid id PK
        string code UK
        string name
    }
    FEATURES {
        uuid id PK
        uuid module_id FK
        string code
        string name
        enum feature_type "BOOLEAN|LIMIT"
    }
    SUBSCRIPTION_PLANS {
        uuid id PK
        string code UK
        string name
        bool is_custom
        bool is_active
    }
    PLAN_FEATURES {
        uuid id PK
        uuid plan_id FK
        uuid feature_id FK
        jsonb config
    }
    TENANT_SUBSCRIPTIONS {
        uuid id PK
        uuid tenant_id FK UK
        uuid plan_id FK
        enum status "TRIALING|ACTIVE|PAST_DUE|SUSPENDED|CANCELLED"
        timestamptz current_period_end
        timestamptz trial_ends_at
    }
    ADD_ONS {
        uuid id PK
        string code UK
        jsonb grants
    }
    TENANT_ADD_ONS {
        uuid id PK
        uuid tenant_id FK
        uuid add_on_id FK
        timestamptz starts_at
        timestamptz ends_at
    }
    TENANT_FEATURE_OVERRIDES {
        uuid id PK
        uuid tenant_id FK
        uuid feature_id FK
        jsonb config
        uuid granted_by FK
        timestamptz expires_at
        text reason
    }
    USAGE_METRICS {
        uuid id PK
        string code UK
        string name
        string unit
    }
    USAGE_RECORDS {
        uuid id PK
        uuid tenant_id FK
        uuid metric_id FK
        bigint value
        date period
    }
    AUDIT_LOGS {
        uuid id PK
        uuid tenant_id FK "nullable = platform-level"
        uuid actor_user_id FK
        string action
        string entity_type
        uuid entity_id
        jsonb before
        jsonb after
        timestamptz created_at
    }
    SUPPORT_ACCESS_LOGS {
        uuid id PK
        uuid tenant_id FK
        uuid platform_admin_user_id FK
        text reason
        string resource
        timestamptz created_at
    }
    FEATURE_CHANGE_LOGS {
        uuid id PK
        uuid tenant_id FK
        uuid changed_by FK
        string change_type
        jsonb details
        timestamptz created_at
    }
```

## Row-level security summary

| Table | Policy |
|---|---|
| `tenant_settings`, `tenant_domains`, `memberships`, `tenant_subscriptions`, `tenant_feature_overrides`, `tenant_add_ons`, `usage_records`, `support_access_logs`, `feature_change_logs` | `tenant_id` matches session context, or platform admin |
| `memberships` | additionally: `user_id` matches session context (own rows) — needed pre-tenant-selection |
| `tenants` | current tenant, platform admin, or caller has an active membership in it |
| `roles` | current tenant, `NULL` tenant (system templates), platform admin, or caller holds that role |
| `audit_logs` | reads tenant-restricted; **inserts unrestricted** (see migration docstring — audit writes must never be blocked by the very policy meant to protect reads of them) |
| `invitations`, `sessions`, `email_verification_tokens`, `password_reset_tokens`, `login_attempts` | **not** row-level-secured — looked up only by unguessable secret token hash, the token itself is the authorization proof |
| `users`, `modules`, `features`, `subscription_plans`, `plan_features`, `add_ons`, `permissions`, `role_permissions`, `usage_metrics` | global catalog/account data, no tenant_id column, no RLS |

## Migrations

Two migrations make up Milestone 1:
1. `1a62ff428104_milestone_1_core_schema.py` — every table, index, and constraint.
2. `57bf2768a62d_row_level_security_policies.py` — RLS enablement and policies.

See `infrastructure/deployment/README.md` for how to run, roll back, and
operate migrations in production, plus connection pooling, backup, and
restore-testing guidance.

## Seed data

`app/db/seed/run.py` (idempotent, safe to re-run) seeds:
- The full permission catalog (`app/modules/permissions/catalog.py`).
- The module/feature/plan/add-on commercial-model catalog
  (`app/db/seed/catalog.py`).
- A platform super admin account.
- A demo tenant ("Rafana Advisory Demo — Fictional Demo Data", Growth
  plan) with three demo users (Tenant Owner, Manager, Sales Agent).

All demo data is clearly labelled as fictional; no real personal
information is used.
