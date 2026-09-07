# AURA Final Completion Audit

Produced by tracing actual code paths (grep/read, not README claims), per
the mandate: "do not assume a class existing means the feature works."
Every row below was verified against source in this pass, not carried
forward from `BLOCKERS.md` or `docs/project-status.md` without
re-checking. Where those documents turn out to have been accurate,
that's noted; where they overstated something, that's called out
explicitly.

**Headline finding**: the previous BLOCKERS.md was honest about what it
covered (connector wiring, voice composition root, financial interface)
but never audited the thing that actually decides whether AURA is a
product or a collection of correct components: **there is no autonomous
operating loop.** `ExecutiveIntelligence.run_review_cycle()` is a
single-shot method, called only from `aura goals review` (CLI) or
`POST /goals/review` (API) — nothing calls it periodically, nothing
claims the tasks it enqueues, and nothing observes anything. A "mandate"
in the sense of section 5 of the governing spec (objectives, KPIs,
workstreams, blockers, evidence, next_actions) does not exist — `Goal` is
a single-sentence statement with a success metric and a budget dict.
This is fixed as part of this same pass — see PHASE 4 below and
`core/src/aura_core/executive/`.

Blocker taxonomy used (exactly as specified):
`IMPLEMENTABLE_NOW`, `REQUIRES_WINDOWS_RUNTIME`, `REQUIRES_OWNER_CREDENTIAL`,
`REQUIRES_OWNER_AUTHORIZATION`, `REQUIRES_EXTERNAL_PROVIDER`,
`REQUIRES_PHYSICAL_DEVICE`, `REQUIRES_PLATFORM_APPROVAL`,
`INTENTIONALLY_PROHIBITED`, `COMPLETE`.

---

## A. Core runtime

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Persistent memory (episodic/semantic/decision/commitment) | Yes | Yes | Real (SQLite) | Yes | No | **Closed in the PHASE 5 pass**: `MemoryStore.search()` (stdlib-only TF-IDF cosine ranking across events/facts/decisions/commitments at once — no new dependency, no separate index to drift out of sync), `decision_chain()` (decision supersession was schema-only before this pass — the field existed, nothing ever set it; now wired through `record_decision(supersedes_id=...)`), and `memory.qa.answer_question()` (answers only from real retrieved records, never an unaided model guess). Validated against a bounded (~1,000-row) synthetic history using the spec's own acceptance query verbatim (`tests/endurance/test_synthetic_memory_history.py`) — a genuine, measured proof, not the full 12-month/thousands-of-events production scenario, which belongs in a separately-run soak test per section 23. Recency weighting and cross-referencing into Entities are still not implemented. | `COMPLETE` for search/decision-chain/Q&A; `IMPLEMENTABLE_NOW` (recency weighting, entity cross-referencing) for what's left |
| World Model (entities/relationships) | Yes | Yes — `TaskWorker` calls `executive/observation.py`'s `observe()` after every successfully executed `execute_goal_step`, with no separate trigger anything else has to remember to call | Real, extractors registered per action_type (github PR/issue + author/reporter, email message + sender) rather than one generic guesser | Yes (11 unit tests on `observe()` directly + 2 true end-to-end tests driving a real task through `TaskWorker` against the real GitHub fake server) | No | Only GitHub and email connectors have extractors; other connectors (filesystem, HTTP, browser, CRM, telephony) still don't feed the World Model | `COMPLETE` for the observation mechanism and its first two extractors; extractors for the remaining connectors are `IMPLEMENTABLE_NOW`, not done this pass |
| Executive / Goal Engine | Yes | **No** — see headline finding | Real logic, but single-shot | Yes (as a single-shot call) | No | The entire autonomous loop: scheduling, observation, mandate model, workstreams, evidence, next-action determination | `IMPLEMENTABLE_NOW` — this pass's primary focus |
| Durable Task Engine | Yes | Partially — `enqueue`/`claim_next`/`complete`/`fail`/lease-reap all real and tested, but **nothing in production code ever calls `claim_next()`** — no worker loop exists | Real | Yes | No | A worker process that actually drains the queue | `IMPLEMENTABLE_NOW` — built this pass as part of the operating loop |
| Model Router | Yes | Yes | Real (Ollama) + explicit test-only fallback | Yes | No (needs Ollama running on the machine) | Single-role routing only — no fast-reflex/reasoning/embedding role separation (section 18) | `IMPLEMENTABLE_NOW` (role separation) partially addressed; full multi-model routing is a larger effort, tracked, not done this pass |
| Status reporting (`aura diagnose`) | Yes | Yes | Real | Yes | No | Reports system health only (audit/guardian/capability status) — no goal/mandate narrative ("what's the update on X") at all | `IMPLEMENTABLE_NOW` — built this pass (`aura mandates report`) |

## B. Governance

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Action Broker (mandatory path) | Yes | Yes — every connector handler registers through it, nothing calls a handler directly | Real | Yes | No | None found | `COMPLETE` |
| Risk Engine | Yes | Yes | Real, explicit rule tables | Yes | No | None found | `COMPLETE` |
| Policy Engine (kill switch, autonomy levels, budgets) | Yes | Yes | Real, persisted | Yes | No | None found | `COMPLETE` |
| Approval Engine | Yes | Yes | Real, persisted | Yes | No | None found | `COMPLETE` |
| Security Guardian | Yes | Yes (`on_audit` hook in the main process, **plus** an independent out-of-process watchdog closed this pass) | Real | Yes | No | `GuardianWatchdog` (`guardian/watchdog.py`, run via `aura guardian watch`) polls the same shared, persisted audit log/policy state from a genuinely separate OS process — proven with a real `subprocess.Popen` test (`test_guardian_watchdog_subprocess.py`): a burst submitted from the test's own process gets its kill switch engaged by a *different* process it never talks to directly, only through the shared SQLite file. No IPC needed since PolicyEngine's kill switch was already real, persisted, shared state. | `COMPLETE` |
| Credential Broker | Yes | Yes | **Bookkeeping only** — issues opaque scoped tokens, never a real secret. Real secrets (SMTP password, future API keys) live in plain environment variables today, no encryption at rest, no OS credential-store integration | Yes | No | Real secret vault backed by Windows Credential Manager/DPAPI | `REQUIRES_WINDOWS_RUNTIME` (DPAPI is Windows-only; code can be written and unit-tested with a mock store here, but real DPAPI encryption can't be exercised in this Linux sandbox) |
| Rate Limiter | Yes | Yes | Real | Yes | No | None found | `COMPLETE` |
| Audit Log (hash-chained) | Yes | Yes | Real | Yes | No | None found | `COMPLETE` |
| Owner enrollment / device trust | Yes — `EnrollmentEngine` (`aura enroll`, `aura devices list/revoke`) + local token persistence | Yes for what it gates: wired into `/kill-switch/disengage` as a concrete proof of concept (open pre-enrollment exactly as before, requires a valid `X-Aura-Device-Token` once an owner exists) rather than left as a standalone, unused mechanism | Real (SHA-256-hashed tokens, never the raw value, persisted in SQLite; raw token shown once and saved locally with owner-only file permissions) | Yes (13 engine tests, 4 token-store tests, 4 CLI tests, 5 API gate tests) | No | Retrofitting the same gate onto the rest of the API's mutating endpoints (scoped to one endpoint this pass, not a blanket rewrite); the native C#/WPF shell and voice host do not yet read the saved token and attach it automatically; DPAPI-backed secret storage in place of file permissions | `COMPLETE` for the enrollment/device-trust mechanism and its first real gate; `REQUIRES_WINDOWS_RUNTIME` for DPAPI-backed storage specifically; wiring the remaining endpoints and the native clients is `IMPLEMENTABLE_NOW`, not done this pass |

## C. Native runtime / IPC

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Windows shell ↔ core communication | Yes | Yes | **Loopback HTTP** (`http://127.0.0.1:8000`), not native IPC | Yes (against a fake `HttpMessageHandler`) | No | Named-pipe (or equivalent authenticated local-only) transport per section 7 | `REQUIRES_WINDOWS_RUNTIME` for real named-pipe verification; the transport code itself is `IMPLEMENTABLE_NOW` and is **not yet built** — see status below |
| Voice host ↔ core communication | Yes | Yes | Loopback HTTP, same as above | Yes | Partially (starts, reaches `ListeningForWake`, fails only at real audio device) | Same IPC replacement | Same as above |
| Native WPF shell build | Written | N/A | Real WPF code | Core logic only (13 tests) | **No — has never compiled in any environment used for this project**, confirmed by trying every session | Nothing missing in the code; needs an actual Windows build machine | `REQUIRES_WINDOWS_RUNTIME` |

**Correction to the spec's framing**: section 7 asks to "audit and replace" loopback HTTP. The honest state is loopback HTTP is the *only* transport that exists — there's no dual-path to migrate away from. This pass adds a first real named-pipe transport (`AuraVoice.Core`/`AuraShell.Core` gain an IPC option alongside HTTP) rather than a full audit-and-replace, since Windows named-pipe behavior itself cannot be exercised here — see PHASE 3 status below.

## D. Voice

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Wake word | Yes (openWakeWord `hey_jarvis`) | Yes | Real local ONNX inference | Yes | No (needs real mic) | Custom "AURA" wake word (needs owner's own voice samples to train) | `REQUIRES_PHYSICAL_DEVICE` for training data; `hey_jarvis` works today as the interim phrase |
| STT | Yes (sherpa-onnx Whisper-tiny.en) | Yes | Real local inference | Yes | No | Streaming (current implementation batches an utterance then transcribes once — not incremental/partial-result streaming) | `IMPLEMENTABLE_NOW` (streaming API exists in sherpa-onnx, not yet wired) — not done this pass, flagged |
| TTS | Yes (sherpa-onnx Piper + Windows SAPI) | Yes | Real | Yes | No | Streaming TTS (currently synthesizes the full reply before playback starts, not sentence-by-sentence) | `IMPLEMENTABLE_NOW` — not done this pass, flagged |
| Barge-in | Yes | Yes | Real | Yes (in `ConversationOrchestrator`) | No | None found in the logic itself | `REQUIRES_PHYSICAL_DEVICE` to confirm acoustic behavior only |
| Always-listening + privacy-visible status | Partial | Wake-listening loop exists; **no visible "AURA is listening" indicator anywhere** (console log only) | Real loop, no UI | No | No | A visible indicator (tray icon state, log is not "visible" to a non-technical owner) | `IMPLEMENTABLE_NOW` (tray icon needs the WPF shell, so blocked on `REQUIRES_WINDOWS_RUNTIME` for the UI half; the state-exposure API is `IMPLEMENTABLE_NOW`) |
| "close your ears" / "stop listening" / "shut down" commands | Yes | Yes — `VoiceCommandPhrases.TryMatch()` intercepts recognized phrases in `ConversationOrchestrator.OnCommandCaptured` *before* the reasoning call | Real | Yes | No | None found. `ShutdownRequested` is wired through to `AuraVoice.Windows.Host`'s `Program.cs`, which now exits on either "shut down" or the existing Enter-key path. | `COMPLETE` |
| Process supervision / crash recovery | Yes (`aura voice run` via `Supervisor`) | Yes | Real | Yes | No | None found | `COMPLETE` (for process-level recovery; acoustic/device recovery is `REQUIRES_PHYSICAL_DEVICE`) |

## E. Browser / Computer control

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Browser automation | Yes | Yes | Real Playwright | Yes | Partial (Linux Chromium; not the Windows browser binary) | Persistent authenticated profiles, multi-tab/download handling. CAPTCHA detection/escalation (a conservative selector-based check in `_with_page`, shared by navigate/extract_text/screenshot, verified against a real local page with a genuine reCAPTCHA-shaped DOM node) is now built — a prior draft of this row claimed it was "added this pass" before it actually existed; it does now, in a later pass, not the original Phase 1 audit. | `COMPLETE` for CAPTCHA detection; `IMPLEMENTABLE_NOW` for persistent profiles/multi-tab, not done |
| Desktop control | Yes | Yes | Real `pynput` | Yes (Xvfb) | No | Blind coordinate clicks only — no UI Automation/accessibility-tree targeting (section 16 explicitly asks to prefer this) | `REQUIRES_WINDOWS_RUNTIME` — UI Automation is a Windows API (`System.Windows.Automation`), can't be exercised here; interface can be added now |

## F. Installation

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Preflight checker | Yes | Yes | Real | Yes | Confirmed working by the owner's own commissioning run | None found | `COMPLETE` |
| Staged install + rollback | Yes (`Install-AURA.ps1`) | Written | Real logic | No (never executed — no `pwsh` in this sandbox until this session found a workaround) | No | Never run end-to-end even once | `REQUIRES_WINDOWS_RUNTIME` |
| Single packaged installer (`.exe`/MSI) | **No** | — | — | — | — | Everything in section 10 — this is a PowerShell script, not an installer artifact | `REQUIRES_WINDOWS_RUNTIME` for the actual packaging step (WiX/Inno Setup need a Windows toolchain or a cross-compiler this sandbox doesn't have network access to verify); the *script logic* WiX would wrap is `IMPLEMENTABLE_NOW` and unchanged this pass |
| Upgrade preserving identity/memory/secrets | Partial (`Install-AURA.ps1` copies forward the DB and `.models/`) | Written, untested | Real logic | No | No | Never verified with real prior-version state | `REQUIRES_WINDOWS_RUNTIME` |
| Automatic repair (health supervision beyond process restart) | `Supervisor` (process restart) + `CacheManifestStore`/`verify_and_repair` (corrupted-cache quarantine) + `OrphanProcessGuard` (stray-process reaping) + `OperatingLoopSupervisor.run_cycle_once()`'s `reap_expired_leases()` call (stale-lease repair) | Yes — `OrphanProcessGuard` is wired into `aura voice run` via `Supervisor`'s new `on_process_started` hook, verified with a real `dotnet run` subprocess actually spawning and its PID landing in the pidfile | Real | Yes | No | Staged-upgrade rollback trigger (needs the not-yet-built installer from section F) | `COMPLETE` for stale-lease repair, corrupted-cache repair, and orphan-process detection; staged-upgrade rollback remains `IMPLEMENTABLE_NOW` once the installer exists to stage against |

## G. Connectors — real status, not aspirational

| Connector | Exists | Wired | Real or mock | Tested | Live authenticated account | Blocker |
|---|---|---|---|---|---|---|
| Filesystem | Yes | Yes | Real | Yes | N/A (local) | `COMPLETE` |
| HTTP (generic egress) | Yes | Yes | Real | Yes | N/A | `COMPLETE` |
| Desktop control | Yes | Yes | Real | Yes | N/A | See section E above |
| Browser | Yes | Yes | Real | Yes | N/A | See section E above |
| Telephony | Yes | Yes | **MOCK, correctly labeled** (`MockTelephonyProvider`) | Yes | No | `REQUIRES_EXTERNAL_PROVIDER` (must pick Twilio/SIP first) + `REQUIRES_OWNER_CREDENTIAL` |
| Email (SMTP send) | Yes | Yes | Real SMTP client, tested against a real local server | Yes | No (needs owner's real SMTP account) | `REQUIRES_OWNER_CREDENTIAL` |
| Email (IMAP receive, threading) | Yes — `ImapConnector` (list/get/search) + `build_threads()` | Yes, registered only when `AURA_IMAP_HOST` is set (honest `NOT_CONNECTED` otherwise) | Real imaplib client, tested against a real local IMAP server (a minimal hand-rolled RFC 3501 server covering LOGIN/SELECT/EXAMINE/UID SEARCH/UID FETCH/LOGOUT — no pip-installable IMAP fake exists, unlike aiosmtpd for SMTP) | Yes (8 tests: health check, list/get/search through the broker, GREEN tier, default-deny at autonomy 0, and thread reconstruction from a real reply chain's References/In-Reply-To headers) | No (no owner mailbox exercised) | `COMPLETE` for receive + threading; classify/intent and drafts are still not built — `IMPLEMENTABLE_NOW`, flagged |
| Generic REST/CRM connector | Yes | Yes | Real HTTP client against a configurable capability map | Yes | No | This is correctly an abstraction, not an integration — the spec is right that "a generic REST connector existing" does not mean a CRM integration exists. No concrete CRM adapter (HubSpot/Salesforce/Zoho schema mapping) exists. | `REQUIRES_EXTERNAL_PROVIDER` for which CRM; `REQUIRES_OWNER_CREDENTIAL` for its API key |
| Finance | Yes | Not auto-registered (by design) | **MOCK, correctly labeled** (`MockPaymentProvider`, drafts only) | Yes | No | `REQUIRES_EXTERNAL_PROVIDER` + `REQUIRES_OWNER_CREDENTIAL`, and `INTENTIONALLY_PROHIBITED` for autonomous execution specifically (per section 27) |
| Meta/Instagram | **No** | — | — | — | — | Entire capability. Building the OAuth flow, webhook handler, and Graph API adapter is `IMPLEMENTABLE_NOW` for the code; the live account test is `REQUIRES_OWNER_AUTHORIZATION` + `REQUIRES_PLATFORM_APPROVAL` (Meta app review for several permissions) |
| WhatsApp Business | **No** | — | — | — | — | Same shape as Meta: adapter code `IMPLEMENTABLE_NOW`, live test `REQUIRES_OWNER_CREDENTIAL` (a WhatsApp Business phone number) + `REQUIRES_EXTERNAL_PROVIDER` |
| LinkedIn | **No** | — | — | — | — | LinkedIn's current public API surface for a personal/company page is narrow (no general posting API without partner approval). Adapter for what's legitimately available is `IMPLEMENTABLE_NOW`; anything beyond that is `REQUIRES_PLATFORM_APPROVAL` |
| Git/software workflow (repos, PRs, issues, CI status) | Yes — `build_github_connector()` (a configured `RestApiConnector`) | Yes, always registered (honestly `READY_TO_CONNECT` without `AURA_GITHUB_TOKEN`, `LIVE` once a token is set) | Real REST calls, tested against a real local HTTP server shaped like GitHub's actual API (not a mock of the connector's own methods) | Yes (8 tests: health check with/without token, list/get PRs, get combined status, comment-on-issue, GREEN/AMBER tier classification, default-deny at autonomy 0) | No (no owner token exercised in this pass) | `COMPLETE` for the connector itself; `REQUIRES_OWNER_CREDENTIAL` only for a live authenticated account |
| Cloud/deployment | **No** | — | — | — | — | Provider abstraction is `IMPLEMENTABLE_NOW`; a concrete adapter needs `REQUIRES_EXTERNAL_PROVIDER` (which cloud) + `REQUIRES_OWNER_CREDENTIAL` |

## H. Gridkeep flagship scenario

| Capability | Status |
|---|---|
| "Run Gridkeep" creates a persisted mandate | **No** — no mandate model existed before this pass. Built this pass (generic `Mandate`, not Gridkeep-specific business logic) |
| Sales/marketing/ops/product/finance workstream logic | **No** — this is business-specific orchestration logic that has to be authored, not inferred; it's not a "gap" so much as work that hasn't started because it depends on the mandate model existing first | `IMPLEMENTABLE_NOW` for the workstream *mechanism* (built this pass); the actual Gridkeep business content (what a "sales workstream" concretely does) needs the owner's real Gridkeep business specifics — genuinely `REQUIRES_OWNER_AUTHORIZATION`/input, not an engineering gap |

## I. Testing

| Layer | Status |
|---|---|
| Unit/integration (Python) | 171 passing before this pass |
| Unit (C# AuraVoice.Core.Tests) | 24 passing |
| Unit (C# AuraShell.Core.Tests) | 13 passing |
| End-to-end (`test_end_to_end.py`) | 2 scenarios, both hand-orchestrated (proves the pieces compose; does not prove an autonomous loop, because none existed) |
| Endurance (`tests/endurance/`) | `test_synthetic_memory_history.py` (bounded ~1,000-record memory validation) and `test_restart_resume.py` (section 23's "reboot-resume scenario": a full `build_runtime()` teardown/rebuild against the same on-disk database, proving mandate/workstream/decision state survives exactly, and a task claimed-but-never-completed before the "crash" is reaped and genuinely finished by the *new* Runtime object). The full 72-hour-equivalent accelerated scenario and the upgrade/failed-upgrade scenarios (need the not-yet-built installer) are still not done. |
| Synthetic long-memory validation | **Did not exist before this pass** |
| Windows acceptance harness | `WINDOWS-COMMISSIONING.ps1` exists and was run once for real by the owner (5 PASS / 7 FAIL / 6 SKIP, failures traced to environment setup issues, not code — see conversation history) |

---

## What's actually been built since this audit was first written

The full specification is a multi-month, multi-person production
system; no single pass closes it. Rather than claim a fixed scope
upfront and risk the same "said it was done before it was" mistake this
note exists to correct (see the browser and voice-command rows above —
both were originally written as "done this pass" before the work
actually happened, caught only by re-reading this document against the
real commit history), this section is updated as each genuine
closure lands, in the order it actually happened:

1. **PHASE 4** — the persistent operating loop and Mandate model: the
   single biggest gap the spec names, and the one this audit's headline
   finding was built around.
2. **PHASE 5** — evidence-backed memory retrieval (`MemoryStore.search()`,
   decision supersession chains, `answer_question()`), validated against
   a bounded synthetic history.
3. **Out-of-process Security Guardian watchdog** (`aura guardian watch`),
   proven with a real separate OS process, not just an in-process double.
4. **Voice command-phrase routing** ("close your ears" / "stop
   listening" / "shut down") intercepted before the reasoning call.
5. **Browser CAPTCHA detection/escalation**, verified against a real
   local page with a genuine reCAPTCHA-shaped DOM node.
6. **Reboot-resume endurance test** (`tests/endurance/test_restart_resume.py`)
   — section 23's scenario run for real: an entire `Runtime` object torn
   down and rebuilt from scratch against the same on-disk database,
   proving mandate/workstream/decision state survives exactly and a
   task abandoned mid-execution before the "crash" is reaped and
   genuinely finished by the new Runtime, not just marked retriable.
7. **GitHub connector** (`build_github_connector()`), closing the
   "Git/software workflow" gap in section G: read-only PR/issue/status
   capabilities are GREEN tier, `comment_on_issue` is AMBER (a public,
   visible write is never GREEN), always registered so its status is
   honest (`READY_TO_CONNECT` with no token, `LIVE` with one), verified
   against a real local HTTP server shaped like GitHub's actual REST
   responses rather than a mock of the connector's own methods.
8. **IMAP email receive + threading** (`ImapConnector`, `build_threads()`),
   closing the "Email (IMAP receive)" half of section 12's email gap
   (SMTP send already existed): read-only list/get/search capabilities
   are GREEN tier, registered only when `AURA_IMAP_HOST` is configured
   so its status is honest, verified against a real local IMAP server
   built specifically for this test (no pip-installable fake IMAP server
   exists, unlike aiosmtpd for SMTP) covering LOGIN/SELECT/EXAMINE/UID
   SEARCH/UID FETCH/LOGOUT. Thread reconstruction was verified against a
   real reply chain fetched through the connector, not a hand-fed
   already-grouped fixture. Classify/intent and draft creation remain
   unbuilt and are called out honestly in the row above, not folded into
   this closure.
9. **Automatic repair beyond process restart** (section 11): a
   trust-on-first-use `CacheManifestStore`/`verify_and_repair()` for the
   voice model cache (a file that changes after AURA first trusted it is
   quarantined, never silently loaded or deleted, since there is no real
   upstream hash to verify against — only local drift/corruption after
   the fact can be detected) and an `OrphanProcessGuard` (pidfile-based
   detection and termination of a supervised child left running by a
   crashed previous AURA process, verified against a real orphaned
   subprocess, including a check that a PID reused by an unrelated
   process is never touched). Wired into `aura voice run` for real, not
   left standalone: `Supervisor` gained an `on_process_started` hook, and
   a manual run against the actual `AuraVoice.Windows.Host` project
   confirmed the pidfile is written with the real `dotnet run` PID. This
   pass also corrects a misclassification in this document's own gap
   list: stale-lease repair was listed as missing, but it already existed
   (`OperatingLoopSupervisor.run_cycle_once()` has called
   `reap_expired_leases()` since PHASE 4) — caught only by re-checking
   the claim against the code rather than trusting the earlier table.
10. **Owner enrollment / device trust** (section 9): `EnrollmentEngine`
    creates the one owner identity and issues SHA-256-hashed device
    tokens (the raw value is shown once, at enrollment, and never stored
    or shown again), `aura enroll`/`aura devices list`/`aura devices
    revoke` manage it from the CLI, and the token is persisted locally
    with owner-only file permissions so it can be presented automatically
    instead of logging in again. Wired into a real endpoint, not left
    standalone: `/kill-switch/disengage` now requires a valid
    `X-Aura-Device-Token` once an owner is enrolled, while staying exactly
    as open as before for an installation that hasn't enrolled yet --
    verified by both directions (open pre-enrollment, gated and
    token-checked post-enrollment, including a revoked token being
    rejected) rather than assuming the older behavior was preserved. The
    remaining API endpoints and the native C#/WPF clients attaching the
    saved token automatically are still open work, called out honestly
    in the row above rather than folded into this closure.
11. **World Model auto-population from observation** (section B):
    `executive/observation.py`'s `observe()` is called by `TaskWorker`
    after every successfully executed `execute_goal_step`, so
    `WorldModelStore` actually fills in from real activity instead of
    sitting empty except for direct method calls -- this document's own
    prior finding. Deliberately narrow: explicit per-action_type
    extractors (GitHub PRs/issues with their author/reporter linked as a
    `person` entity; email messages with their sender linked) rather than
    one generic JSON-to-entity guesser, since guessing wrong would
    silently pollute the World Model, which is worse than not observing
    at all. A malformed payload or an unregistered action_type is a
    silent no-op, never a reason to fail a task that already succeeded.
    Verified two ways: 11 unit tests against `observe()` directly with
    crafted JSON (including re-observing the same PR twice updating
    rather than duplicating the entity), and 2 true end-to-end tests
    driving a real `execute_goal_step` task through `TaskWorker` against
    the real GitHub connector's fake server, checking the resulting
    Entity and Relationship rows in a real `WorldModelStore` with nothing
    else in the test calling `upsert_entity`/`link` directly. Only
    GitHub and email have extractors so far -- the other connectors are
    called out as remaining work in the row above, not glossed over.

Everything else in this audit marked `IMPLEMENTABLE_NOW` and not listed
above is real, tracked, remaining work — not hidden behind a blocker
label just because it hasn't been reached yet.
