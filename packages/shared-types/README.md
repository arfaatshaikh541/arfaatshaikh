# @gridkeep/shared-types

Placeholder for OpenAPI-generated TypeScript types (`openapi-typescript`
against `apps/api`'s `/openapi.json`).

**Status at Milestone 1:** not wired up yet. `apps/web/lib/types.ts` holds
hand-written types for the Milestone 1 API surface (auth, tenancy,
memberships, subscriptions, entitlements). Generating this package's
contents from the live OpenAPI schema is a Milestone 2+ housekeeping item
once the API surface is large enough to make hand-maintained types costly.
