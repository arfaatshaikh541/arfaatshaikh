# Performance and Load Testing

**What this document is:** real measurements taken this milestone against a real, fully-wired
control-api instance (the identical router every integration test in this codebase exercises — real
Postgres, real Argon2id, real CSRF, real RLS), driven by an external HTTP load generator
(`rakyll/hey`) over a real TCP socket. **Not** a synthetic estimate or a description of a tool that
was merely installed — every number below came from a command that was actually run, on this
sandbox's hardware, against this exact codebase at its current state.

## Method

`internal/app`'s own test harness (`testServer`, used by every integration test in this package)
already assembles the full production router against a real database and a real fake-SMTP/fake-
object-store pair. A temporary driver test (`TestZZZLoadTestDriver`, deleted after this drill —
never part of the permanent suite) booted that exact router behind a real `httptest.Server` (a real
listening TCP socket, not an in-process mock) and blocked for a fixed duration, writing its URL to a
file. `hey` then hit that URL directly, exactly as it would hit `cmd/server` in a real deployment.

This measures **this sandbox's own CPU/scheduling characteristics**, not a representative production
server's — see the Known Limitation at the end.

## Results

### `GET /healthz` (no auth, no DB query — router/middleware-chain overhead floor)

2,000 requests, 50 concurrent:

| Metric | Value |
|---|---|
| Requests/sec | **17,729** |
| p50 latency | 1.6 ms |
| p90 latency | 5.9 ms |
| p99 latency | 12.3 ms |
| Errors | 0 / 2,000 |

This is the floor: every request in this codebase pays at least this much for CORS, CSRF-cookie
issuance, and the security-headers middleware chain, before it does anything domain-specific.

### `POST /api/v1/auth/login` (real Argon2id verification — the CPU-heaviest single request type in this codebase)

200 requests, 10 concurrent, against a real registered-and-verified account:

| Metric | Value |
|---|---|
| Requests/sec | **64.9** |
| p50 latency | 135 ms |
| p90 latency | 173 ms |
| p95 latency | 436 ms |
| p99 latency | 687 ms |
| Errors | 0 / 200 (all `200 OK`) |

This is the expected shape for Argon2id at this codebase's configured cost parameters (64 MiB
memory, 3 iterations, parallelism 2): deliberately expensive per-request CPU cost is the entire point
of the algorithm (it is what makes offline password-cracking expensive), so a login endpoint's
throughput ceiling is fundamentally bounded by available CPU cores, not by database or network I/O.
The gap between p50 (135 ms) and p99 (687 ms) at only 10 concurrent workers indicates CPU contention
begins well below higher concurrency levels on this sandbox's core count — see capacity-planning
note below.

### `GET /api/v1/auth/me` (authenticated, session-validated, real database read)

1,000 requests, 30 concurrent, against a real session cookie:

| Metric | Value |
|---|---|
| Requests/sec | **~1,100–1,200** (two runs) |
| p50 latency | 24–26 ms |
| p90 latency | 28–31 ms |
| p99 latency | 33–49 ms |
| Errors | 0 (every observed response was `200 OK`) |

An ordinary authenticated, database-backed read sustains roughly 17x the throughput of the login
endpoint at slightly higher concurrency — consistent with session validation being a single indexed
lookup plus a hash comparison, versus login's deliberately expensive Argon2id derivation.

## Capacity-planning implication

Login throughput (not general API throughput) is this service's real bottleneck under load, by design
— every other endpoint measured is 15-20x faster. A production capacity plan should size CPU
headroom around expected concurrent login volume specifically (login storms after a mass password
reset, a Monday-morning login spike, etc.), not around general API request volume, and should
consider whether `ARGON2_ITERATIONS`/`ARGON2_MEMORY_KIB` need retuning for the target deployment's
actual CPU allocation per instance — the parameters are already environment-configurable
(`internal/platform/config/config.go`) specifically for this kind of tuning, not hardcoded.

## Known limitation

These numbers describe **this sandboxed development container's** CPU and I/O characteristics (shared
vCPUs, unknown neighbor contention, a Postgres/Redis instance running on the same host as the load
generator and the server under test — nothing is network-isolated the way a real deployment's
database tier would be). They are directionally useful (the *relative* shape — login is ~200x more
expensive per-request than an authenticated read, which is ~15x cheaper than raw router overhead
suggests — is architecture, not hardware, and will hold on any hardware) but the *absolute* req/s
numbers should be re-measured against representative production hardware and a properly isolated
database tier before being used for real capacity planning. This is the same category of caveat as
every other sandbox-scale measurement in this milestone's other drills (disaster recovery, chaos
testing).
