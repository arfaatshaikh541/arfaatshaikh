# Entity Relationship Summary — Milestone 1

This covers the tables implemented in Milestone 1 (multi-tenancy, auth,
RBAC, tenant settings, subscriptions, audit log). Later milestones add
leads, pipeline, scoring, workflows, booking, etc. on top of this
foundation, always with a `tenant_id` foreign key on tenant-owned tables.

```
tenants
  id                uuid PK
  slug              text UNIQUE NOT NULL         -- used in public URLs
  name              text NOT NULL
  legal_name        text
  status            enum(active,suspended,archived) NOT NULL DEFAULT 'active'
  timezone          text NOT NULL DEFAULT 'Asia/Dubai'
  currency          text NOT NULL DEFAULT 'AED'
  created_at        timestamptz NOT NULL
  updated_at        timestamptz NOT NULL

tenant_settings
  id                uuid PK
  tenant_id         uuid FK -> tenants.id UNIQUE NOT NULL
  logo_url          text
  brand_primary_color   text DEFAULT '#F97316'
  brand_secondary_color text DEFAULT '#111827'
  contact_email     text
  contact_phone     text
  business_hours    jsonb NOT NULL DEFAULT '{}'   -- per-day open/close, tenant-defined shape
  locale            text NOT NULL DEFAULT 'en'
  data_retention_days integer NOT NULL DEFAULT 730
  privacy_text      text
  created_at        timestamptz NOT NULL
  updated_at        timestamptz NOT NULL

tenant_domains
  id                uuid PK
  tenant_id         uuid FK -> tenants.id NOT NULL
  domain            text UNIQUE NOT NULL
  is_primary        boolean NOT NULL DEFAULT false
  verified_at       timestamptz

subscription_plans                                -- platform catalog, not tenant-owned
  id                uuid PK
  code              text UNIQUE NOT NULL           -- e.g. 'starter', 'growth'
  name              text NOT NULL
  price_cents       integer NOT NULL
  currency          text NOT NULL DEFAULT 'AED'
  features          jsonb NOT NULL DEFAULT '[]'    -- flexible feature-key list
  is_active         boolean NOT NULL DEFAULT true

subscriptions
  id                uuid PK
  tenant_id         uuid FK -> tenants.id NOT NULL
  plan_id           uuid FK -> subscription_plans.id NOT NULL
  status            enum(trialing,active,past_due,canceled) NOT NULL
  current_period_end timestamptz
  created_at        timestamptz NOT NULL

tenant_features
  id                uuid PK
  tenant_id         uuid FK -> tenants.id NOT NULL
  feature_key       text NOT NULL
  enabled           boolean NOT NULL DEFAULT true
  UNIQUE(tenant_id, feature_key)

users                                              -- global identity, can join many tenants
  id                uuid PK
  email             citext UNIQUE NOT NULL
  hashed_password   text NOT NULL
  is_platform_super_admin boolean NOT NULL DEFAULT false
  is_active         boolean NOT NULL DEFAULT true
  email_verified_at timestamptz
  two_factor_enabled boolean NOT NULL DEFAULT false
  two_factor_secret_encrypted text                 -- null unless enrolled; encrypted at rest
  failed_login_count integer NOT NULL DEFAULT 0
  locked_until      timestamptz
  created_at        timestamptz NOT NULL
  updated_at        timestamptz NOT NULL

roles
  id                uuid PK
  tenant_id         uuid FK -> tenants.id NOT NULL
  name              text NOT NULL
  slug              text NOT NULL                  -- e.g. 'owner','administrator'
  is_system         boolean NOT NULL DEFAULT false  -- seeded default, cannot be deleted
  created_at        timestamptz NOT NULL
  UNIQUE(tenant_id, slug)

permissions                                        -- global catalog
  id                uuid PK
  code              text UNIQUE NOT NULL            -- e.g. 'leads.view'
  description       text NOT NULL

role_permissions
  role_id           uuid FK -> roles.id NOT NULL
  permission_id     uuid FK -> permissions.id NOT NULL
  PRIMARY KEY(role_id, permission_id)

memberships
  id                uuid PK
  tenant_id         uuid FK -> tenants.id NOT NULL
  user_id           uuid FK -> users.id NOT NULL
  role_id           uuid FK -> roles.id NOT NULL
  status            enum(active,invited,suspended) NOT NULL DEFAULT 'active'
  created_at        timestamptz NOT NULL
  updated_at        timestamptz NOT NULL
  UNIQUE(tenant_id, user_id)

invitations
  id                uuid PK
  tenant_id         uuid FK -> tenants.id NOT NULL
  email             citext NOT NULL
  role_id           uuid FK -> roles.id NOT NULL
  invited_by_user_id uuid FK -> users.id NOT NULL
  token_hash        text NOT NULL
  status            enum(pending,accepted,revoked,expired) NOT NULL DEFAULT 'pending'
  expires_at        timestamptz NOT NULL
  created_at        timestamptz NOT NULL

sessions                                           -- one row per issued refresh token
  id                uuid PK
  user_id           uuid FK -> users.id NOT NULL
  refresh_token_hash text NOT NULL
  replaced_by_id    uuid FK -> sessions.id          -- rotation chain, for reuse detection
  user_agent        text
  ip_address        text
  expires_at        timestamptz NOT NULL
  revoked_at        timestamptz
  created_at        timestamptz NOT NULL

email_verification_tokens
  id                uuid PK
  user_id           uuid FK -> users.id NOT NULL
  token_hash        text NOT NULL
  expires_at        timestamptz NOT NULL
  consumed_at       timestamptz

password_reset_tokens
  id                uuid PK
  user_id           uuid FK -> users.id NOT NULL
  token_hash        text NOT NULL
  expires_at        timestamptz NOT NULL
  consumed_at       timestamptz

login_attempts                                     -- rate limiting / lockout
  id                uuid PK
  email             citext NOT NULL
  ip_address        text NOT NULL
  success           boolean NOT NULL
  created_at        timestamptz NOT NULL

audit_logs                                         -- immutable, append-only
  id                uuid PK
  tenant_id         uuid FK -> tenants.id           -- null for platform-level events
  actor_user_id     uuid FK -> users.id
  event_type        text NOT NULL                   -- e.g. 'super_admin.tenant.viewed'
  entity_type       text
  entity_id         text
  metadata          jsonb NOT NULL DEFAULT '{}'      -- never contains secrets/tokens
  correlation_id    uuid
  created_at        timestamptz NOT NULL
```

## Relationships

- `Tenant 1—1 TenantSettings`
- `Tenant 1—N TenantDomains, TenantFeatures, Subscriptions, Roles, Memberships, Invitations, AuditLogs`
- `User N—M Tenant` through `Membership` (a user can hold one membership per
  tenant; `UNIQUE(tenant_id, user_id)`)
- `Membership N—1 Role`, `Role N—M Permission` through `role_permissions`
- `Session N—1 User` (a user can have many active sessions/devices)
- Platform Super Admin is **not** a row in `roles`/`memberships` — it is
  `users.is_platform_super_admin`, checked independently of tenant context,
  because it is not scoped to any single tenant.

## Indexing / Constraints Notes

- `UNIQUE(tenant_id, user_id)` on `memberships` prevents duplicate
  membership rows and gives us a fast existence check for the isolation
  dependency.
- `UNIQUE(tenant_id, slug)` on `roles` and `UNIQUE(tenant_id, feature_key)`
  on `tenant_features` are tenant-aware uniqueness constraints as required.
- B-tree indexes on all `tenant_id` FK columns (Postgres does not
  auto-index FKs) plus `sessions.user_id`, `sessions.refresh_token_hash`,
  `audit_logs.tenant_id, created_at`.
- `audit_logs` has no `updated_at`/soft-delete columns — rows are
  immutable and never mutated or deleted by the application.
