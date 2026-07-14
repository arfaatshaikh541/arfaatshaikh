# ERD addendum — Milestone 7

Covers Module 17 (Onboarding). Every tenant so far has been created one
of two ways: `POST /platform/tenants` (a platform super admin creates
it on a business's behalf) or `app.seed.py` (demo data). Neither is a
real self-serve path - there was no way for a prospective customer to
sign themselves up. This milestone adds that, plus a short setup
wizard for the freshly created tenant.

## Self-serve signup

### `signup_attempts`

Append-only, IP-keyed - mirrors the existing `login_attempts` /
`public_form_attempts` rate-limit pattern rather than inventing a new
one. Unlike `public_form_attempts` (scoped to one tenant's enquiry
form), signup happens before any tenant exists, so this table has no
`tenant_id` column at all.

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| ip_address | text | indexed |
| created_at | timestamptz | indexed |

Limit: 5 signups per IP per 60 minutes (stricter than the public
enquiry form's 20-per-15-minutes, since a successful signup creates a
whole tenant - roles, pipeline stages, services, a default workflow
rule - not just one lead row).

### `tenant_settings.onboarding_completed_at`

Nullable timestamp, added to the existing `TenantSettings` model.
`NULL` means the tenant hasn't finished (or has never seen) the setup
wizard. Set once, server-side, by a dedicated `POST
/tenants/me/onboarding/complete` endpoint (idempotent - calling it
again after completion is a no-op that returns the original
timestamp) rather than letting the client PATCH an arbitrary
timestamp through `TenantSettingsUpdate`. The dashboard reads this
field (via the existing `GET /tenants/me/settings`) to decide whether
to show a "finish setting up your workspace" banner.

### `POST /auth/signup`

Public, unauthenticated, alongside `/auth/login` and
`/invitations/accept`. Request: business name, slug, owner name/email/
password (same shape and validation as `TenantCreate`, minus the
platform-admin-only fields). Behavior:

1. Rate-limit check against `signup_attempts` by client IP.
2. `TenantService.self_signup(...)` - thin wrapper around the existing
   `create_tenant_with_owner(...)`, the same one `/platform/tenants`
   and `app.seed.py` already use, so a self-serve tenant gets
   identical defaults (roles, pipeline stages, services, business
   hours backfill, default workflow rule) with **one** difference:
   `verify_owner_email=False` - a self-serve owner's email is
   unverified until they click the link, whereas a platform-admin-
   created tenant trusts the admin's judgment and starts verified.
3. Sends a verification email via the existing
   `AuthService.start_email_verification()` - reused exactly as-is
   from the existing forgot-password/verify-email flow, not
   reimplemented.
4. Logs the new owner in immediately (`AuthService.login()` +
   `set_auth_cookies`, the same pattern `POST /invitations/accept`
   already uses for a brand-new user) - the account is usable right
   away; email verification is a nudge, not a gate, matching how
   platform-admin-created accounts already work today (no verification
   gate exists anywhere else in the app).

No CAPTCHA - matching the existing public enquiry form's stance
(rate-limit + append-only attempt log is the only abuse defense
anywhere in this codebase so far). `/auth/signup` is added to the
CSRF-exempt path list alongside `/auth/login`, for the same reason:
it submits fresh credentials rather than relying on ambient cookie
authority.

## Onboarding wizard

Almost entirely a frontend flow over pre-existing endpoints - the only
new backend surface is the completion endpoint above. Steps: welcome,
confirm the seeded default services (read-only list - editing happens
on the existing Services page), set business hours (the same
`business_hours` JSONB the Milestone 5 settings page already edits,
via `PATCH /tenants/me/settings`), optionally invite teammates
(`POST /tenants/me/invitations`, already exists), done (`POST
/tenants/me/onboarding/complete`). Every step but the last is a thin
form over an endpoint that already existed before this milestone; the
wizard's own logic is just sequencing, plus the completion flag and
the dashboard banner that reads it.
