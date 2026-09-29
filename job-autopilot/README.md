# JOB AUTOPILOT

A self-hosted system that discovers real job postings, matches them against your
**verified** candidate profile, completes employer application forms in a real
Chromium browser with answers grounded in your own facts, and records a submission
**only when the employer's site confirms it**.

It is designed to run on a server (Docker Compose) so it keeps working while your
laptop is off. You manage it from a browser or phone through the dashboard.

## What is real, and what is not supported

| Capability | Status |
|---|---|
| Discovery from Greenhouse, Lever and Ashby employer boards (official public APIs) | Implemented. Unit-tested against the documented API shapes. **Live fetch not yet validated from the build environment (egress blocked).** |
| Applying via Greenhouse/Lever/Ashby hosted application forms (Playwright/Chromium) | Implemented generic form engine. Tested end-to-end against local fixture forms. **Live submission on a real employer board not yet validated.** |
| CAPTCHA / OTP / MFA | Detected → `VERIFICATION_REQUIRED`; the browser is held and you complete it yourself from your phone, then automation resumes. **Never bypassed.** |
| Employer portal login test (you supply login URL + selectors + success indicator) | Implemented; CONNECTED only when the indicator is observed. |
| LinkedIn, Indeed, Bayt, GulfTalent, Naukrigulf | **NOT AUTOMATABLE**: their terms prohibit automated use. No connector exists. |
| AI provider (Anthropic / OpenAI / Ollama) | Optional, for narrative answers only. Every output passes the grounding validator. Default: NOT CONFIGURED. |
| OCR of scanned (image-only) PDFs | NOT SUPPORTED. |

See [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) for the acceptance checklist, including which
items have been verified and which still need live validation on your server.

## Documents

* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): architecture, schema, security model, workers, state machine
* [`docs/PLATFORMS.md`](docs/PLATFORMS.md): per-platform assessment
* [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md): production deployment
* [`docs/OPERATIONS.md`](docs/OPERATIONS.md): first-time setup and daily use
* [`docs/CLOUD_RUNTIME.md`](docs/CLOUD_RUNTIME.md): 24/7 runtime, remote browser, human verification from your phone, recovery
* [`docs/SECURITY_REVIEW.md`](docs/SECURITY_REVIEW.md): security review of the cloud runtime

## Quick start without Docker (plain Python)

```bash
python3.12 -m venv venv && source venv/bin/activate      # Python 3.11 or 3.12
pip install -e ".[embedded]"
autopilot setup                                          # config, master key, Chromium, built-in database
autopilot create-admin --email you@example.com
autopilot run                                            # open http://127.0.0.1:8000 (Ctrl+C stops)
```
Details, 24/7 on a server with systemd: [`docs/RUN_WITHOUT_DOCKER.md`](docs/RUN_WITHOUT_DOCKER.md).

## Quick start with Docker (server)

```bash
cp .env.example .env                   # set POSTGRES_PASSWORD
docker compose build
mkdir -p secrets
docker run --rm job-autopilot:latest gen-master-key > secrets/master.key
sudo chown 1001:1001 secrets/master.key && sudo chmod 600 secrets/master.key  # back this file up!
docker compose --profile tls up -d     # Caddy obtains HTTPS for JOBAP_DOMAIN
docker compose exec web autopilot create-admin --email you@example.com
```

With `--profile tls`, Caddy serves the dashboard over HTTPS at `JOBAP_DOMAIN`; otherwise put your own TLS
proxy in front of `127.0.0.1:8000` (see `docs/DEPLOYMENT.md`). Then follow `docs/OPERATIONS.md`.

## Development

```bash
pip install -e '.[test]'
export JOBAP_TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost/autopilot_test
pytest
```

Tests run against a real PostgreSQL database and a real Chromium. Browser tests use local
HTML fixtures (`tests/fixtures/forms`). These exercise this code but are **not** a
validation of any real platform.
