# AI provider architecture

## Why this exists

The platform must never require a paid AI API to function, and must never
call one silently. This module (`apps/api/app/services/ai_provider.py`) is
the single place that decision is enforced.

```
AIProvider (abstract)
├── OllamaProvider       - talks to a self-hosted Ollama server. Default.
├── LocalModelProvider   - alias of OllamaProvider (Ollama IS the local-
│                          model runtime this platform targets)
└── ExternalProvider     - disabled by construction; a documented
                           extension point, not a real implementation
```

`get_ai_provider(settings)` is the only supported way to obtain a provider.
Configuration:

| Env var | Default | Effect |
|---|---|---|
| `WOI_AI_MODE` | `local` | `local` -> `OllamaProvider`. `external` -> `ExternalProvider` unless also opted in (below). |
| `WOI_EXTERNAL_AI_ENABLED` | `false` | Even with `AI_MODE=external`, this must ALSO be `true` before `get_ai_provider` returns anything but the disabled `ExternalProvider` stub. This codebase ships **no concrete paid-API implementation** - the flag exists to document the extension point and its guard, not to unlock a hidden integration. |
| `WOI_OLLAMA_BASE_URL` | `http://localhost:11434` | Where `OllamaProvider` looks for a local Ollama daemon. |
| `WOI_OLLAMA_MODEL` | `llama3.1` | Model name passed to Ollama's `/api/generate`. Must be pulled locally (`ollama pull llama3.1`) for generation to succeed - the API only ever talks to whatever is already running on that host, it never downloads or manages models itself. |
| `WOI_OLLAMA_TIMEOUT_SECONDS` | `30` | Request timeout against the local daemon. |

## API surface

Mounted at `/api/v1/intelligence` (`apps/api/app/api/routes/ai_provider.py`),
both endpoints authenticated (`get_current_user`):

- `GET /status` - reports `{mode, provider, available, external_ai_enabled}`.
  `available` is a live check (`OllamaProvider.is_available()` pings
  `/api/tags`), not a cached or assumed value.
- `POST /generate` - `{prompt}` in, `{available, provider, text, error}` out.
  Rate-limited (20/min per client) the same way auth endpoints are.

Neither endpoint is wired into the evidence-grounded assistant
(`/api/v1/assistant/query`, see `docs/architecture/ARCHITECTURE.md`). That
pipeline's entire value is that it never generates text beyond verbatim,
cited source quotations - bolting a generative model onto it would blur
exactly the guarantee it exists to make, and there is no way to fully
verify such a merge end-to-end in an environment where the generative side
cannot even be installed (see below). It is deliberately a separate,
standalone capability today.

## What was and wasn't verified in this pass

- **Unavailability path (real, not mocked):** this sandbox has no Ollama
  daemon and none could be installed - `curl https://ollama.com/install.sh`
  is rejected by the environment's egress policy, and the only relevant
  PyPI package (`ollama`) is a client SDK, not the server. `is_available()`
  and `generate()` were run for real against that absence
  (`apps/api/tests/test_ai_provider.py`) and correctly report `available:
  false` with a descriptive error - never an exception, never a fabricated
  response. This was also exercised over real HTTP end-to-end (registered
  a user, logged in, called `GET /api/v1/intelligence/status` and
  `POST /api/v1/intelligence/generate`) - see `docs/FINAL_AUDIT_ULTIMATE.md`.
- **Success path (real HTTP, stub server):** `apps/api/tests/test_ai_provider_ollama_contract.py`
  runs an actual local HTTP server (Python's `http.server`, not a mock of
  `httpx`) that implements Ollama's documented `/api/tags` and
  `/api/generate` response shapes, and confirms `OllamaProvider` parses a
  real conforming HTTP response correctly. **This is not a test of the real
  Ollama binary** - it proves the client code is correct against the
  documented contract, not that the real server behaves identically in
  every respect. Running against a real Ollama installation with a pulled
  model is `NOT VERIFIED` in this pass.
- **`ExternalProvider`** is verified to always report unavailable and never
  attempt a network call, including when both `AI_MODE=external` and
  `EXTERNAL_AI_ENABLED=true` are set - by inspection of the code path (it
  unconditionally returns the disabled stub) and by test.
