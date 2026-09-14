# Frontend foundation

The web application uses Next.js App Router with Server Components by default and narrowly scoped Client Components for forms, session state, routing, and API requests.

`@world-of-islam/ui` owns accessible primitives. `@world-of-islam/shared-types` owns transport-facing TypeScript contracts. Locale routing begins at `/en` and `/ar`; unsupported unprefixed routes are redirected to English by middleware.

Authentication remains backend-authoritative. The browser receives an opaque HttpOnly session cookie and an in-memory CSRF token. On reload, `GET /api/v1/auth/csrf` rotates and returns a fresh CSRF token for the authenticated session. No session credential is stored in localStorage.
