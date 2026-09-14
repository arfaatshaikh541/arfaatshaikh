# Authentication architecture

World of Islam uses opaque server-side sessions. Raw session, verification and reset tokens are never persisted. Only HMAC-SHA-256 token hashes are stored, using the application secret as a pepper.

Passwords use Argon2id with explicit memory, time and parallelism costs. Authentication responses are deliberately generic. Password-reset requests do not disclose whether an account exists.

Browser sessions use an `HttpOnly`, `SameSite=Lax` cookie. Production requires the `Secure` flag. State-changing authenticated requests require a session-bound CSRF token in `X-CSRF-Token`. Logout, password reset and user-requested revocation invalidate server records rather than merely deleting browser cookies.

Verification and reset messages enter a transactional email outbox. Unit 3 records delivery work but does not claim an external email provider is configured. The worker-side delivery adapter belongs to a later Milestone 1 unit.

Redis-backed fixed-window limits protect registration, login and reset initiation. Production fails closed if the limiter is unavailable; development may continue so local dependency outages remain debuggable.
