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
| Persistent memory (episodic/semantic/decision/commitment) | Yes | Yes | Real (SQLite) | Yes | No | **Closed in the PHASE 5 pass**: `MemoryStore.search()` (stdlib-only TF-IDF cosine ranking across events/facts/decisions/commitments at once — no new dependency, no separate index to drift out of sync), `decision_chain()` (decision supersession was schema-only before this pass — the field existed, nothing ever set it; now wired through `record_decision(supersedes_id=...)`), and `memory.qa.answer_question()` (answers only from real retrieved records, never an unaided model guess). Validated against a bounded (~1,000-row) synthetic history using the spec's own acceptance query verbatim (`tests/endurance/test_synthetic_memory_history.py`) — a genuine, measured proof, not the full 12-month/thousands-of-events production scenario, which belongs in a separately-run soak test per section 23. **Recency weighting and entity cross-referencing are now built too**: `search()` blends cosine relevance with an exponential recency decay (floored at 25% of the original score, so recency is a tie-breaker among comparably relevant results, never a veto over a genuinely stronger old match), and — when a `WorldModelStore` is passed in — tags each result with the World Model entity ids its text mentions by name. Wired all the way through: `aura memory search`/`ask` and `/memory/search`/`/memory/ask` now pass `runtime.world_model` in, not left as a library-only capability nobody's callers use. | `COMPLETE` — search, decision-chain, Q&A, recency weighting, and entity cross-referencing are all built, tested, and wired into the CLI/API |
| World Model (entities/relationships) | Yes | Yes — `TaskWorker` calls `executive/observation.py`'s `observe()` after every successfully executed `execute_goal_step`, with no separate trigger anything else has to remember to call | Real, extractors registered per action_type (github PR/issue + author/reporter, email message + sender, telephony call + recipient, cloud deployment + service) rather than one generic guesser | Yes (15 unit tests on `observe()` directly + 2 true end-to-end tests driving a real task through `TaskWorker` against the real GitHub fake server) | No | Filesystem, generic HTTP, browser, and the generic CRM/REST connector still have no extractor. Checked filesystem specifically (not just assumed alongside browser): `read_file`/`write_file`/`list_dir` deliberately return raw file content / a plain newline-joined listing as the handler message, asserted exactly by existing tests (`test_connectors_filesystem_http.py`), because that raw content is the useful behavior for these actions ("read this file and tell me what it says"). Extracting a "file" entity would mean the same trade browser already declined: sacrificing a directly useful, tested plain-content response for marginal entity value (a `list_dir` result alone is just filenames, with no hash/mtime to make a genuinely useful entity). Generic CRM/HTTP have no fixed schema AURA itself controls (whatever the configured vendor's API returns), so an extractor there could only honestly target one specific vendor's shape once one is chosen. | `COMPLETE` for the observation mechanism and four extractors (github, email, telephony, cloud); filesystem/CRM/HTTP/browser extraction is blocked on the same kind of real trade-off (an established response contract, or no fixed schema to target), not on missing engineering |
| Executive / Goal Engine | Yes | **No** — see headline finding | Real logic, but single-shot | Yes (as a single-shot call) | No | The entire autonomous loop: scheduling, observation, mandate model, workstreams, evidence, next-action determination | `IMPLEMENTABLE_NOW` — this pass's primary focus |
| Durable Task Engine | Yes | Partially — `enqueue`/`claim_next`/`complete`/`fail`/lease-reap all real and tested, but **nothing in production code ever calls `claim_next()`** — no worker loop exists | Real | Yes | No | A worker process that actually drains the queue | `IMPLEMENTABLE_NOW` — built this pass as part of the operating loop |
| Model Router | Yes | Yes -- `ModelRole.REASONING/FAST/EMBEDDING`, `aura model embed`, `POST /model/embed` | Real (Ollama for reasoning/fast text generation and real `/api/embeddings` calls) + explicit test-only fallback for each role, never silently outside `AURA_ENV=test` | Yes (10 new router tests covering FAST falling back to REASONING when unconfigured vs. actually using a configured FAST provider, and EMBEDDING's own fallback/refusal behavior; 1 CLI + 2 API tests) | No (needs Ollama running on the machine) | The remaining four of the architecture doc's seven capability classes (frontier reasoning, coding, vision, speech) need hosted-provider credentials this codebase doesn't have; embeddings are not yet used to enhance `MemoryStore.search()`'s ranking (that stays TF-IDF, honestly) | `COMPLETE` for the fast-reflex/reasoning/embedding split named in section 18; frontier/coding/vision/speech roles are `REQUIRES_OWNER_CREDENTIAL` (pick a hosted provider) + `REQUIRES_EXTERNAL_PROVIDER`, not attempted |
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
| Owner enrollment / device trust | Yes — `EnrollmentEngine` (`aura enroll`, `aura devices list/revoke`) + local token persistence | Yes, fully: every one of the API's 17 POST endpoints (governance, tasks, goals, mandates, memory, chat, voice) is gated via a single shared `require_device_token` FastAPI dependency, open before enrollment and requiring a valid `X-Aura-Device-Token` after; every GET stays open (read-only). Both C# apps (`AuraShell`, `AuraVoice.Windows.Host`) attach `AURA_DEVICE_TOKEN` automatically via `DeviceTokenHeader.AttachIfConfigured` on both the IPC and TCP client paths | Real (SHA-256-hashed tokens, never the raw value, persisted in SQLite; raw token shown once and saved locally with owner-only file permissions) | Yes (13 engine tests, 4 token-store tests, 4 CLI tests, 5 kill-switch gate tests, 4 cross-endpoint gate tests covering before/after/valid-token/read-only-never-gated, 3+3 C# `DeviceTokenHeader` tests) | No | DPAPI-backed secret storage in place of file permissions | `COMPLETE` — the enrollment/device-trust mechanism, every mutating endpoint's gate, and both native clients attaching the token automatically are all built and tested; `REQUIRES_WINDOWS_RUNTIME` only for DPAPI-backed storage specifically |

## C. Native runtime / IPC

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Windows shell ↔ core communication | Yes | Yes | **Unix domain socket** (`aura serve`, `IpcHttpClientFactory` in both C# apps), not loopback TCP -- the same HTTP/1.1 + SSE code (`AuraApiClient`, `HttpProviders`) runs completely unmodified over it | Yes: 4 new Python tests (a real `aura serve` subprocess hit over its real Unix socket, including a check that no TCP port is listening) + 4 new C# tests (a real listening socket accepting a real connection and exchanging real HTTP bytes) | No (this transport specifically -- Windows itself is `REQUIRES_WINDOWS_RUNTIME`, see below) | Auto-selecting the socket without an explicit `AURA_CORE_SOCKET` env var; named-pipe framing was deliberately not built (see rationale) | `COMPLETE`: chose AF_UNIX sockets over named pipes because Windows has shipped native AF_UNIX support since build 17063 (GA since version 1809), and .NET's `UnixDomainSocketEndPoint` / Python's `socket.AF_UNIX` have both supported it since .NET Core 3.0 / Python 3.9 -- one implementation, not two, runs unmodified on both platforms, and the Linux half is now genuinely proven, not just asserted |
| Voice host ↔ core communication | Yes | Yes | **Unix domain socket**, same mechanism and same `AuraShell.Core.IpcHttpClientFactory` as above (`AuraVoice.Windows.Host`'s `AURA_CORE_SOCKET` env var) | Yes, same 8 tests above cover the shared transport code | Partially (starts, reaches `ListeningForWake`, fails only at real audio device) | Same remaining item: no auto-selection without an explicit env var | `COMPLETE`, same rationale as above |
| Native WPF shell build | Written | N/A | Real WPF code | Core logic only (15 tests, +2 for the new IPC client) | **No — has never compiled in any environment used for this project**, confirmed by trying every session | Nothing missing in the code; needs an actual Windows build machine | `REQUIRES_WINDOWS_RUNTIME` |

**Correction to the spec's framing, superseded**: section 7 asks to
"audit and replace" loopback HTTP. An earlier draft of this document
noted loopback HTTP was the only transport and that named-pipe framing
would be needed to replace it. That plan changed once actually
implemented: rather than building a second, Windows-only named-pipe
protocol that could never be tested in this sandbox, this pass replaced
loopback TCP with a Unix domain socket -- a transport that satisfies
"local, not localhost" exactly as literally as a named pipe would
(filesystem-path-addressed, filesystem-permission-controlled, never
touches the TCP/IP stack), runs as the *same* code on both Windows and
Linux (Windows has shipped native AF_UNIX support since build 17063,
GA since version 1809; .NET Core 3.0+ and Python 3.9+ both support it
there), and — critically — is the one flavor of "not loopback TCP" that
this Linux sandbox can actually exercise for real. `aura serve` binds it
by default; `curl`/browsers/other TCP-only tooling still get plain
loopback TCP via `aura serve --host`. See `core/src/aura_core/ipc.py`'s
module docstring for the full rationale.

## D. Voice

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Wake word | Yes (openWakeWord `hey_jarvis`) | Yes | Real local ONNX inference | Yes | No (needs real mic) | Custom "AURA" wake word (needs owner's own voice samples to train) | `REQUIRES_PHYSICAL_DEVICE` for training data; `hey_jarvis` works today as the interim phrase |
| STT | Yes (sherpa-onnx Whisper-tiny.en) | Yes | Real local inference | Yes | No | **Correction to the earlier claim on this row**: sherpa-onnx's streaming API (`OnlineRecognizer`) does exist, but it's built for streaming-capable model architectures (e.g. a streaming zipformer transducer) -- Whisper is fundamentally an offline encoder-decoder with no incremental mode to switch on. Genuine STT streaming needs downloading and wiring a different model entirely, not an API-mode flip on the model already in use. | `REQUIRES_EXTERNAL_PROVIDER`-adjacent in practice (a different, larger streaming-model download is needed); not attempted this pass -- the Whisper-based batch pipeline remains the real, working path |
| TTS | Yes (sherpa-onnx Piper + Windows SAPI) | Yes | Real | Yes | No | True incremental audio-frame streaming needs a streaming-capable vocoder Piper/VITS isn't; the achievable approximation -- speaking each sentence as soon as it's generated rather than waiting for the full reply -- is now built (`ConversationOrchestrator`'s optional `generateResponseStreaming` path + `SentenceSplitter`) | `COMPLETE` for sentence-level streaming (the honest, achievable form of "streaming TTS" with this build's models); full model-level audio streaming needs a different TTS architecture, `REQUIRES_EXTERNAL_PROVIDER`-adjacent, not attempted |
| Barge-in | Yes | Yes | Real | Yes (in `ConversationOrchestrator`) | No | None found in the logic itself | `REQUIRES_PHYSICAL_DEVICE` to confirm acoustic behavior only |
| Always-listening + privacy-visible status | Yes for the state-exposure API | Yes -- the voice host pushes every `VoiceSessionController.StateChanged` transition to a real `GET`/`POST /voice/state` pair on the core API (fire-and-forget; a failed push logs a warning and never stops the voice loop), so any local client (a future tray icon, `aura status`, this endpoint directly) can read real current state without any direct reference to the voice host process | Real (backed by the same `status` registry `/status` already exposes) | Yes (6 Python tests: unknown-before-first-report, round-trip, every real state value accepted, an unrecognized state rejected, gated once enrolled for the POST, never gated for the GET; 2 C# `AuraApiClient` tests) | No | The visible indicator itself (a tray icon UI) still needs the WPF shell | `COMPLETE` for the state-exposure API (the thing that was actually `IMPLEMENTABLE_NOW`); the tray icon UI remains `REQUIRES_WINDOWS_RUNTIME`, unchanged |
| "close your ears" / "stop listening" / "shut down" commands | Yes | Yes — `VoiceCommandPhrases.TryMatch()` intercepts recognized phrases in `ConversationOrchestrator.OnCommandCaptured` *before* the reasoning call | Real | Yes | No | None found. `ShutdownRequested` is wired through to `AuraVoice.Windows.Host`'s `Program.cs`, which now exits on either "shut down" or the existing Enter-key path. | `COMPLETE` |
| Process supervision / crash recovery | Yes (`aura voice run` via `Supervisor`) | Yes | Real | Yes | No | None found | `COMPLETE` (for process-level recovery; acoustic/device recovery is `REQUIRES_PHYSICAL_DEVICE`) |

## E. Browser / Computer control

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Browser automation | Yes | Yes | Real Playwright, including `launch_persistent_context(profile_dir)` for persistent authenticated sessions, real concurrent multi-Page operation for `browser.extract_text_multi`, and real `page.expect_download()`-based file download handling (`browser.download_file`, sandboxed to `AURA_BROWSER_DOWNLOAD_DIR`, `save_as` path-escape rejected) | Yes (6 new download tests: trigger-selector mode, direct-URL mode, no-download-dir-configured denial, path-escape rejection, AMBER tier, default-deny) | Partial (Linux Chromium; not the Windows browser binary) | Upload flows (the other half of "upload/save-file") are still not built. CAPTCHA detection/escalation (a conservative selector-based check in `_with_page`, shared by navigate/extract_text/screenshot, verified against a real local page with a genuine reCAPTCHA-shaped DOM node) is built. | `COMPLETE` for CAPTCHA detection, persistent profiles, multi-tab, and file downloads; `IMPLEMENTABLE_NOW` for upload flows, not done |
| Desktop control | Yes | Yes | Real `pynput` for coordinate-based control; `UiAutomationProvider` interface (`find_element`/`click_element`, resolving a named/roled element to screen coordinates before delegating to the same real `pynput` click) backed by `MockUiAutomationProvider`, an explicitly-labeled fixed in-memory accessibility tree, not a real platform backend | Yes (Xvfb; 4 new tests: honest `NOT_CONNECTED` with no provider configured, real element lookup + no-match case, real click resolved through the mock tree against the live display, GREEN/AMBER tier + default-deny) | No | A real Windows UI Automation (or Linux AT-SPI) backend implementing `UiAutomationProvider` is not built — this sandbox cannot exercise either | `COMPLETE` for the interface, the governed find/click-by-element pipeline, and the mock backend; a real per-platform backend is `REQUIRES_WINDOWS_RUNTIME` for Windows UI Automation specifically |

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
| Telephony | Yes | Yes | **MOCK, correctly labeled** (`MockTelephonyProvider`); `health_check()` reports `READY_TO_CONNECT` (not `LIVE`) for the mock, and every `CallRecord` carries `provider: "mock"` | Yes | No | `REQUIRES_EXTERNAL_PROVIDER` (must pick Twilio/SIP first) + `REQUIRES_OWNER_CREDENTIAL` |
| Email (SMTP send) | Yes | Yes | Real SMTP client, tested against a real local server | Yes | No (needs owner's real SMTP account) | `REQUIRES_OWNER_CREDENTIAL` |
| Email (IMAP receive, threading, classify, drafts) | Yes — `ImapConnector` (list/get/search/save_draft) + `build_threads()` + `classify_message_intent()` (`aura email classify`, `POST /email/classify`, both gated) | Yes, registered only when `AURA_IMAP_HOST` is set (honest `NOT_CONNECTED` otherwise); classification always available since it only needs the already-wired Model Router | Real imaplib client, tested against a real local IMAP server (a minimal hand-rolled RFC 3501 server covering LOGIN/SELECT/EXAMINE/UID SEARCH/UID FETCH/LOGOUT/APPEND — no pip-installable IMAP fake exists, unlike aiosmtpd for SMTP); `save_draft` does a real RFC 3501 APPEND with the `\Draft` flag, folder name always quoted (imaplib does not quote mailbox arguments itself); classification is a real Model Router call against a fixed 5-category list, never fabricating a category outside it | Yes (12 IMAP tests, including 4 for save_draft: real append content, default vs custom folder, AMBER tier, default-deny; 9 classify tests: 6 unit against a scripted provider including the fixed-category-list refusal case, 1 CLI, 2 API) | No (no owner mailbox exercised) | `COMPLETE` for receive, threading, classify, and drafts |
| Generic REST/CRM connector | Yes | Yes | Real HTTP client against a configurable capability map | Yes | No | This is correctly an abstraction, not an integration — the spec is right that "a generic REST connector existing" does not mean a CRM integration exists. No concrete CRM adapter (HubSpot/Salesforce/Zoho schema mapping) exists. | `REQUIRES_EXTERNAL_PROVIDER` for which CRM; `REQUIRES_OWNER_CREDENTIAL` for its API key |
| Finance | Yes | Not auto-registered (by design) | **MOCK, correctly labeled** (`MockPaymentProvider`, drafts only); `health_check()` reports `READY_TO_CONNECT` (not `LIVE`) for the mock | Yes | No | `REQUIRES_EXTERNAL_PROVIDER` + `REQUIRES_OWNER_CREDENTIAL`, and `INTENTIONALLY_PROHIBITED` for autonomous execution specifically (per section 27) |
| Meta/Instagram | Yes -- `build_meta_connector()` (Facebook Page: posts, comments, publish, reply) + `InstagramConnector` (real two-step Graph API media publish: create container, then publish it) | Yes, both always registered (`AURA_META_TOKEN`/`AURA_INSTAGRAM_TOKEN`), honest `READY_TO_CONNECT`/`LIVE` per token presence | Real REST calls against real local servers shaped like Meta Graph API v19 and the Instagram Graph API's two-step publish endpoints | Yes (6 Meta tests: health both states, real read through the broker, real write with body verification + AMBER tier, GREEN read tiers, default-deny; 6 Instagram tests: health both states, real two-step publish returning the final media_id, a publish-step failure reported honestly with the already-created container id, AMBER tier, default-deny) | No (no live Meta app/token exercised) | None found for either connector | `COMPLETE` for the Facebook Page connector and Instagram's publish flow; a live account is `REQUIRES_OWNER_AUTHORIZATION` (OAuth consent) + `REQUIRES_PLATFORM_APPROVAL` (Meta App Review for most real permissions, including Instagram content publishing) |
| WhatsApp Business | Yes -- `build_whatsapp_connector()` (Cloud API: text messages, template messages, media messages, phone number status) | Yes, always registered (`AURA_WHATSAPP_TOKEN`) | Real REST calls against a real local server shaped like the WhatsApp Cloud API; `send_template_message`/`send_media_message` build the real Cloud API request body (template name/language/components; media type + id-or-link + caption) from named params rather than a raw passthrough body | Yes (8 tests: health both states, real text send with body verification + AMBER tier, GREEN read tier, default-deny, real template body construction + AMBER tier, real media body construction + AMBER tier, honest denial when neither media_id nor media_link is given) | No | None found | `COMPLETE` for text, template, and media messages; a live account is `REQUIRES_OWNER_CREDENTIAL` (a real WhatsApp Business phone number, and pre-approved template definitions for templates specifically) + `REQUIRES_EXTERNAL_PROVIDER` |
| LinkedIn | Yes -- `build_linkedin_connector()` (profile read, UGC post share) | Yes, always registered (`AURA_LINKEDIN_TOKEN`) | Real REST calls against a real local server shaped like LinkedIn's REST API | Yes (5 tests: health both states, real profile read + GREEN tier, real share with body verification + AMBER tier, default-deny) | No | RestApiConnector only sets one static header, so LinkedIn's recommended `X-Restli-Protocol-Version`/`LinkedIn-Version` headers aren't sent (same documented limitation as the GitHub connector) | `COMPLETE` for what LinkedIn's public API legitimately allows without partner approval; anything beyond `ugcPosts`/`me` is `REQUIRES_PLATFORM_APPROVAL`; a live account needs `REQUIRES_OWNER_AUTHORIZATION` (OAuth consent) |
| Git/software workflow (repos, PRs, issues, CI status) | Yes — `build_github_connector()` (a configured `RestApiConnector`) | Yes, always registered (honestly `READY_TO_CONNECT` without `AURA_GITHUB_TOKEN`, `LIVE` once a token is set) | Real REST calls, tested against a real local HTTP server shaped like GitHub's actual API (not a mock of the connector's own methods) | Yes (8 tests: health check with/without token, list/get PRs, get combined status, comment-on-issue, GREEN/AMBER tier classification, default-deny at autonomy 0) | No (no owner token exercised in this pass) | `COMPLETE` for the connector itself; `REQUIRES_OWNER_CREDENTIAL` only for a live authenticated account |
| Cloud/deployment | Yes -- `CloudConnector`/`CloudProvider` + `MockCloudProvider` | Yes, always registered (mirrors the telephony mock's shape: safe to auto-register since nothing real is ever touched) | **MOCK, correctly labeled** (in-memory deployment ledger; `deploy`/`rollback` genuinely manage which version is "live" per service+environment, not just a label on one record); `health_check()` reports `READY_TO_CONNECT` (not `LIVE`) for the mock, and every `Deployment` carries `provider: "mock"` | Yes (7 tests: deploy/rollback AMBER + status GREEN classification, default-deny at autonomy 0, a real deploy executing through the broker, deploy-chain previous-id tracking, rollback genuinely restoring the prior deployment to live, an unknown deployment id reported honestly) | No | A real cloud provider adapter (AWS/GCP/Azure/Fly.io/etc.) | `COMPLETE` for the provider abstraction and deploy/rollback state machine; a concrete adapter needs `REQUIRES_EXTERNAL_PROVIDER` (which cloud) + `REQUIRES_OWNER_CREDENTIAL` |

## H. Gridkeep flagship scenario

| Capability | Status |
|---|---|
| "Run Gridkeep" creates a persisted mandate, without a generic goal-form | **Yes** — `mandates.create_from_directive("Run Gridkeep")` (also `aura mandates run` / `POST /mandates/run`) parses the directive, creates a `draft` mandate titled "Run Gridkeep" with mission "Operate and grow Gridkeep", scaffolds the 13 standard operating departments as objectives, and persists through a real restart (fresh `MandateEngine` against the same `database_url`) | `COMPLETE` for the directive-parsing and department-scaffolding mechanism; the mandate deliberately cannot `activate()` until real KPIs/constraints for the actual business are supplied, since those are facts about a real company this system has no way to invent |
| Sales/marketing/ops/product/finance workstream logic | **No** — this is business-specific orchestration logic that has to be authored, not inferred; it's not a "gap" so much as work that hasn't started because it depends on the mandate model existing first | `IMPLEMENTABLE_NOW` for the workstream *mechanism* (built this pass); the actual Gridkeep business content (what a "sales workstream" concretely does) needs the owner's real Gridkeep business specifics — genuinely `REQUIRES_OWNER_AUTHORIZATION`/input, not an engineering gap |
| "What's happening with Gridkeep?" answered from real state, not chat memory | **Yes** — `POST /chat` recognizes an executive-status question via `parse_status_query()`, resolves it to a real mandate via `find_by_company()`, and renders the real `MandateReport` as text, all before the query ever reaches the model; an unmatched company name gets an honest "no mandate found" rather than a generic chatbot answer | `COMPLETE` |

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
12. **Memory recency weighting + entity cross-referencing** (section A):
    the two items left over after the PHASE 5 memory-retrieval pass.
    `MemoryStore.search()` now blends TF-IDF cosine relevance with an
    exponential recency decay, floored at 25% of the original score
    specifically so recency can only break ties among comparably
    relevant results, never let a much weaker but newer match outrank a
    genuinely strong old one (a real design fix this pass found: an
    unfloored decay let exactly that happen for old-enough records,
    caught by a test written to check it, not assumed safe). When a
    `WorldModelStore` is passed to `search()`, each result is tagged with
    the ids of every World Model entity its text names -- retrieval
    doesn't stop at "which record matches" without also surfacing "what
    this is about." Wired all the way through rather than left as a
    library-only capability: `aura memory search`/`ask`,
    `/memory/search`/`/memory/ask`, and `memory.qa.answer_question()`
    all pass `runtime.world_model` through now. 6 new unit tests, plus
    the full existing memory-search/QA/endurance suite re-run to confirm
    the refactor changed no existing ranking behavior.
13. **Native local IPC transport** (section 7, the item this document's
    original headline finding named alongside the operating loop as the
    two biggest gaps): `aura serve` now binds a Unix domain socket by
    default and both C# apps (`AuraShell`, `AuraVoice.Windows.Host`)
    connect to it via a new `IpcHttpClientFactory` using
    `SocketsHttpHandler.ConnectCallback`, with the entire existing
    HTTP/1.1 + JSON + SSE-streaming client/server code
    (`AuraApiClient`, `HttpProviders`, every test against them)
    running completely unmodified over the new transport. Chose AF_UNIX
    sockets over named pipes deliberately: Windows has shipped native
    AF_UNIX support since build 17063 (GA since version 1809 / Windows
    Server 2019), and .NET Core 3.0+ / Python 3.9+ both support it there
    too, so one implementation runs on both platforms instead of two,
    and — the deciding factor — it's the one that this Linux sandbox can
    actually build *and verify for real*, not just write and hope. Proven
    two ways: a real `aura serve` subprocess hit over its real socket
    file via httpx (including a check that no TCP port ends up
    listening, the actual point of the exercise), and a real C# test
    with a genuine listening `Socket`/`UnixDomainSocketEndPoint`
    accepting a real connection and exchanging real HTTP bytes through
    `IpcHttpClientFactory`. 4 new Python tests, 4 new C# tests (2 per
    app), full Python suite and both C# test suites re-run green. `aura
    serve --host` keeps the old loopback-TCP behavior available for
    tooling (curl, browsers) that only speaks HTTP-over-TCP.
14. **Every mutating API endpoint gated by device trust** (section 9,
    completing item 10 above): the device-token check that previously
    protected only `/kill-switch/disengage` now sits on all 17 POST
    endpoints via one shared `require_device_token` FastAPI dependency
    (`gated = [Depends(require_device_token)]`), so covering a new route
    going forward is one list reference, not a copy-pasted check that
    could be forgotten. Every GET stays open -- read-only endpoints
    expose nothing an unauthenticated local caller could cause harm
    with. Both native clients now attach the token automatically: a new
    `DeviceTokenHeader.AttachIfConfigured()` (mirrored in
    `AuraShell.Core` and `AuraVoice.Core` since the latter has no
    dependency on the former) sets `X-Aura-Device-Token` from
    `AURA_DEVICE_TOKEN` on both the IPC and TCP client construction
    paths in `App.xaml.cs` and `Program.cs`, so an owner who runs `aura
    enroll` doesn't wake up to every request from their own shell/voice
    apps failing with 401. Verified as an actual cross-endpoint property,
    not endpoint-by-endpoint: one test sweeps a representative sample of
    endpoints before enrollment (all open), one sweeps them after
    enrollment with no token (all 401, including one new sample --
    `/voice/wake-word/check` -- not covered by the item-10 tests), one
    sweeps them with the real token (all succeed), and one confirms
    GET endpoints are never gated even after enrollment. Full suite: 302
    passed (298 baseline + 4 new), plus 3 new tests per C# app for
    `DeviceTokenHeader`, all green, zero regressions -- confirmed
    specifically that no pre-existing test (none of which ever enrolls
    an owner) started failing once every POST endpoint gained a gate.
15. **Voice "always listening" state-exposure API** (section 8): closes
    the audit's flagged gap ("no visible indicator anywhere, console log
    only") on the side that's actually `IMPLEMENTABLE_NOW` -- the tray
    icon UI itself still needs the WPF shell. `AuraVoice.Windows.Host`
    now pushes every `VoiceSessionController.StateChanged` transition to
    a new `GET`/`POST /voice/state` pair on the core API, fire-and-forget
    (a failed push logs a warning and never stops or blocks the voice
    loop, since visibility must never come at the cost of the thing it's
    reporting on). `GET /voice/state` is read-only and ungated, backed by
    the same `status` registry `/status` already exposes, so any local
    client -- a future tray icon, `aura status`, this endpoint directly
    -- can see real current state without any reference to the voice
    host process. 6 new Python tests (unknown-before-first-report,
    round-trip, every real state value accepted, an unrecognized state
    rejected with 422, POST gated once enrolled, GET never gated) and 2
    new C# `AuraApiClient` tests. Full suite and both C# test suites
    re-run green.
16. **Model Router role separation** (section 18): `ModelRole.REASONING/
    FAST/EMBEDDING` narrows the architecture doc's seven-class table to
    the three this build can actually route between without a hosted-
    provider credential. `select_provider(role)` uses a configured FAST
    provider when given and falls back to REASONING's provider when not
    (today's un-split behavior, unchanged for every existing caller that
    never passes a role). `embed()` is new: a real `OllamaEmbeddingProvider`
    (genuine `/api/embeddings` calls) plus a `DeterministicTestEmbeddingProvider`
    (a SHA-256-derived, unit-normalized, explicitly-not-a-real-model
    vector, gated by the same `allow_test_provider` discipline the text
    test provider already uses) for `AURA_ENV=test`. Wired end to end,
    not left as dead code in the router's constructor: `aura model embed
    <text>` and `POST /model/embed` (gated) both make a real call through
    the router. `AURA_OLLAMA_FAST_MODEL` / `AURA_OLLAMA_EMBEDDING_MODEL`
    (defaulting to `nomic-embed-text`) configure the two new roles; both
    optional. 10 new router tests (FAST falls back to REASONING when
    unconfigured vs. genuinely uses a configured FAST provider; EMBEDDING's
    own fallback-to-deterministic and fail-closed-outside-test-mode
    behavior; determinism and distinctness of the test vector), 1 CLI
    test, 2 API tests. Embeddings are not yet used to enhance
    `MemoryStore.search()`'s own ranking -- that stays TF-IDF, called out
    honestly rather than silently implied.
17. **Browser persistent authenticated profiles + multi-tab** (section
    E): `BrowserConnector` still launches a fresh browser process per
    action (no cross-request session to manage, thread-safety, or
    lifecycle problems to introduce), but now optionally points every
    launch at the same on-disk Chromium profile directory
    (`AURA_BROWSER_PROFILE_DIR`, `launch_persistent_context()`), so
    cookies and login sessions genuinely persist across separate
    actions -- the actual shape "persistent authenticated profiles"
    needs. `browser.extract_text_multi` drives real concurrent multi-tab
    operation: every target URL gets its own `Page` open within one
    shared browser context in a single action, each handled and reported
    independently, so a CAPTCHA or failure on one tab never sinks the
    others. Verified for real, not assumed: one test proves a cookie set
    by a first launched-and-closed browser process is read back by a
    genuinely separate second process pointed at the same profile
    directory, and a contrast test proves the *default* (no profile)
    correctly starts fresh every time -- the persistent case is proving
    something real, not something that would pass regardless. Building
    the cookie test surfaced a real distinction worth recording: a
    session cookie (no `Max-Age`/`Expires`) is correctly discarded by a
    genuine browser restart even with a persistent profile -- that's
    real Chromium behavior, not a connector bug, and the test uses a
    `Max-Age` cookie to match how real login sessions are actually shaped.
    Multi-tab is verified against two different real local pages in one
    call, confirming per-tab isolation of the CAPTCHA escalation. 5 new
    connector tests (cookie contrast, persistent-profile proof, multi-tab
    success, multi-tab allowlist denial). Download handling remains
    unbuilt, called out in the row above.
18. **Cloud/deployment connector** (section G's remaining "No" row):
    `CloudProvider`/`CloudConnector` + `MockCloudProvider`, the same
    "interface now, real backend later" shape as the existing finance
    and telephony mocks. `deploy`/`rollback` are AMBER tier,
    `get_deployment_status` is GREEN; always registered, since an
    in-memory ledger is safe to auto-register the way a real cloud
    credential wouldn't be. Genuinely manages which deployment is live
    per (service, environment) rather than just labeling records: a
    second deploy records the first deployment's id as
    `previous_deployment_id`, and rolling back the second restores the
    first to `status: live` -- verified directly, not assumed from the
    rollback call merely returning success. 7 new tests. Picking and
    authorizing a real cloud provider (AWS/GCP/Azure/etc.) remains
    `REQUIRES_EXTERNAL_PROVIDER` + `REQUIRES_OWNER_CREDENTIAL`, called
    out honestly in the row above.
19. **World Model extractors for telephony and cloud** (extending item 11's
    observation mechanism, closing two of the "remaining connectors" it
    named): `telephony.call` now links the recipient phone number as a
    `person` entity to a `phone_call` entity; `cloud.deploy`/`rollback`/
    `get_deployment_status` link a `cloud_deployment` entity to the
    `cloud_service` it deploys, with two deployments of the same
    service correctly sharing one service entity rather than creating a
    duplicate. Required a small, deliberate connector change first:
    `TelephonyConnector.call()` returned a plain human-readable string
    (`"call {id} to {to}: {status}"`), which `observe()` cannot parse --
    changed to `json.dumps(record.to_dict())`, the same shape
    GitHub/email/cloud already return, verified against no existing test
    asserting the old string (there wasn't one). CRM/HTTP/browser
    extraction was deliberately not attempted this pass -- see the row
    above for why forcing one would mean guessing a schema, not closing
    a real gap. 6 new tests (4 observation unit tests, plus the existing
    telephony/cloud connector suites re-run to confirm the message-format
    change broke nothing).
20. **Sentence-level streaming TTS** (section 8): a genuine, deliberate
    architecture finding first, then the achievable fix. Neither Whisper
    (STT) nor Piper/VITS (TTS) in this build has a real incremental
    streaming mode -- sherpa-onnx's `OnlineRecognizer` API exists but
    targets streaming-capable model architectures this build doesn't
    use, and there is no "streaming Piper" at all. Corrected this
    document's earlier framing of both rows to say so plainly rather
    than leave "not yet wired" implying it's a simple switch. Built the
    achievable approximation instead: `ConversationOrchestrator` gained
    an optional `generateResponseStreaming` delegate (backward
    compatible -- every existing caller and all 43 pre-existing tests
    are unaffected, since it defaults to null and falls back to the
    original single-SpeakAsync-of-the-full-reply behavior) that speaks
    each sentence as soon as the model finishes producing it, via a new
    `SentenceSplitter` (pure, 8 unit tests). Barge-in mid-reply is
    honored immediately: a sentence queued after an interruption is
    checked against controller state and silently dropped rather than
    spoken late. Wired into `AuraVoice.Windows.Host/Program.cs` for
    real. 4 new `ConversationOrchestrator` tests (sequential sentence
    playback, barge-in stopping mid-stream, the no-punctuation and
    empty-response fallback paths). One infrastructure issue surfaced
    and fixed along the way, not a logic bug: the full test class was
    intermittently flaky against a stale incremental build (`bin`/`obj`
    from a prior compile); a clean rebuild made it and 4 more repeat
    runs consistently green, confirming the code itself was correct all
    along. Both C# suites clean-rebuilt and re-run green (AuraVoice.Core.Tests
    55, AuraShell.Core.Tests 20).
21. **Meta, WhatsApp, and LinkedIn connectors** (section G's three
    remaining "No" rows): the same real-vendor-configuration-of-
    RestApiConnector pattern the GitHub connector established --
    `build_meta_connector()` (Facebook Page posts/comments/publish/
    reply), `build_whatsapp_connector()` (Cloud API text messages),
    `build_linkedin_connector()` (profile read, UGC post share). Reads
    are GREEN tier, writes (`meta.publish_post`, `meta.reply_to_comment`,
    `whatsapp.send_message`, `linkedin.share_post`) are AMBER, all
    always registered so their status is honest (`READY_TO_CONNECT`
    without a token, `LIVE` with one) via `AURA_META_TOKEN`/
    `AURA_WHATSAPP_TOKEN`/`AURA_LINKEDIN_TOKEN`. Verified against three
    real local HTTP servers, each shaped like the real vendor API it
    stands in for -- not mocks of the connector's own methods -- 16 new
    tests total (6 Meta, 5 WhatsApp, 5 LinkedIn) covering both health
    states, a real read through the broker, a real write with its body
    verified against what the fake server actually received, correct
    GREEN/AMBER classification, and default-deny at autonomy 0.
    Deliberately scoped narrower than the vendor names might suggest,
    called out rather than glossed over: Instagram's own publish flow
    (a genuinely different two-step create-then-publish API, not a
    single-request capability) is not built; WhatsApp message templates
    and media messages are not built, only plain text; LinkedIn is
    limited to what's available without Partner Program approval.
22. **Email intent classification** (the "classify" half of section
    12's email gap; IMAP receive/threading were closed earlier this
    session): `classify_message_intent()` was always a wiring gap, not
    a missing capability -- the Model Router it needs already existed.
    Classifies into exactly one of five fixed categories (inquiry,
    complaint, action_required, informational, spam) via the REASONING
    role; a response that doesn't parse to one of them is reported as
    "unclassified" rather than mapped to whichever category looks
    closest -- the same never-fabricate discipline
    `executive.parse_plan()` already applies to model output driving a
    real decision. Wired end to end: `aura email classify <subject>
    <body>` and `POST /email/classify` (gated like every other mutating
    endpoint). 9 new tests (6 unit against a scripted provider,
    including the fixed-category-list refusal case and an empty-response
    case; 1 CLI; 2 API, including the device-trust gate). Drafts (saving
    a message via IMAP `APPEND`) remain unbuilt, called out honestly in
    the row above.
23. **Browser file downloads and IMAP drafts** (section E's and G's
    remaining "not built" items): `BrowserConnector.download_file`
    supports both a `trigger_selector` (clicking a real link/button) and
    a direct-URL mode, wrapped in Playwright's real
    `page.expect_download()`, saved only inside a configured
    `AURA_BROWSER_DOWNLOAD_DIR` with any `save_as` that would escape that
    directory rejected outright — tested against a real local HTTP server
    serving a genuine downloadable file, not a mocked download event (6
    new tests). `ImapConnector.save_draft` does a real RFC 3501 `APPEND`
    with the `\Draft` flag against a hand-rolled fake IMAP server
    extended to parse `APPEND`'s literal-length syntax; the connector now
    always quotes the folder name, since imaplib does not do this itself
    and an unquoted multi-word folder name breaks the raw IMAP command
    line — a genuine bug caught by a real test failure, not a hypothetical
    (4 new tests). Both actions are AMBER tier, both denied by default at
    autonomy 0, matching every other write-capable connector.
24. **Instagram two-step publish and WhatsApp templates/media** (section
    G's last two named gaps): `InstagramConnector` implements the real
    Graph API flow the "Meta" row explicitly said needed its own
    handling — `POST /{ig_user_id}/media` to create a container, then
    `POST /{ig_user_id}/media_publish` to publish it — reporting a
    failure at whichever step actually failed rather than retrying or
    silently reporting partial success. `WhatsAppConnector` gained
    `send_template_message` and `send_media_message` as their own
    action_types (not just "pass a raw body to send_message"), so the
    World Model and autonomy policy can tell a template send apart from a
    media send apart from free text — each builds its real Cloud API
    request body from named params (template name/language/components;
    media type plus exactly one of media_id/media_link, plus an optional
    caption), and a media message with neither id nor link is denied with
    an honest reason rather than sent malformed. Both new connectors
    verified against real local HTTP servers shaped like their real
    vendor APIs (12 new tests total: 6 Instagram, 6 WhatsApp), both AMBER
    tier, both denied by default at autonomy 0. Neither can honestly
    claim more than this without an owner's real access token
    (`REQUIRES_OWNER_CREDENTIAL`) and, for Instagram, Meta App Review
    (`REQUIRES_PLATFORM_APPROVAL`).
25. **UI Automation interface for desktop control** (section 16's
    preference for accessibility-tree targeting over blind coordinates,
    section E's remaining desktop-control gap): a new
    `UiAutomationProvider` interface (`connectors/ui_automation.py`)
    defines `find_element(name=..., role=..., automation_id=...)` against
    a real per-platform backend not yet built (Windows UI Automation and
    Linux AT-SPI are both `REQUIRES_WINDOWS_RUNTIME`/genuinely
    unexercisable headless here) -- the same "interface now, real backend
    later" shape as `MockPaymentProvider`/`MockTelephonyProvider`/
    `MockCloudProvider`. `DesktopControlConnector` gained two new
    action_types, `computer_control.find_element` (GREEN tier, resolves
    an element's real screen geometry) and `computer_control.click_element`
    (AMBER tier, resolves an element then clicks its center through the
    same real `pynput` call `computer_control.click` already uses) --
    both honestly report `NOT_CONNECTED` rather than silently falling
    back to coordinates when no provider is configured. Verified against
    `MockUiAutomationProvider`, an explicitly-labeled fixed in-memory
    accessibility tree, and (for the click path) a real Xvfb display (4
    new tests: not-connected without a provider, real element lookup
    including the no-match case, a real click resolved through the mock
    tree and executed against the live display, GREEN/AMBER tier
    classification, default-deny at autonomy 0).
26. **Connector-truthfulness fix for the three "mock, correctly labeled"
    providers**: `TelephonyConnector`, `CloudConnector`, and
    `FinanceConnector` were each reporting `health_check() == LIVE` for
    their mock backend (`MockTelephonyProvider`/`MockCloudProvider`/
    `MockPaymentProvider`), which a real owner querying `/status` or
    `GET /connectors` could genuinely misread as "a real phone call/cloud
    deployment/payment backend is connected." Fixed to report
    `READY_TO_CONNECT` for the mock case in all three, matching this
    project's own rule that `LIVE` means a real authenticated external
    operation, never a simulation. `CallRecord` and `Deployment` also
    gained a `provider` field (`"mock"` today) serialized into every
    outcome, so an audit-log/World-Model consumer can always tell a
    simulated call or deployment apart from a real one even though the
    Action Broker still reports the governed request itself as EXECUTED.
    6 existing tests updated to assert the corrected status (2 connector
    unit tests, 1 each for finance/cloud, plus the 2 runtime-level tests
    that exercise the real `build_runtime()`/`/connectors` path, which
    had been asserting the wrong thing all along). Also: with PowerShell
    now installable in this sandbox (a prior network-policy block that
    had made `install/Install-AURA.ps1` and `WINDOWS-COMMISSIONING.ps1`
    entirely unparseable here has lifted), both scripts were, for the
    first time, actually parsed with PowerShell's own AST parser --
    zero syntax errors in either -- and `WINDOWS-COMMISSIONING.ps1` was
    actually executed end to end on this Linux sandbox. Doing so
    surfaced one real, platform-independent bug: its very first check
    (`install\preflight.py`) was invoked via a bare `python` instead of
    the `$venvPython` the script computes one line earlier and uses
    everywhere else -- would have run against whatever `python` happens
    to resolve to on the owner's PATH (frequently absent or wrong on a
    real Windows machine, where the launcher is often `py` and the venv
    interpreter is a separate binary), not the project's own venv. Fixed
    to use `$venvPython` consistently. Every other failure from that
    Linux run (pytest showing "No module named pytest" via the `python`
    fallback since Linux venvs don't have `Scripts\python.exe`;
    `Start-Process -WindowStyle` refusing to run on a non-Windows pwsh
    edition) is a genuine Linux-only artifact of running a
    Windows-targeted script outside Windows, confirmed by reading the
    surrounding code, not a bug that would reproduce on the real target
    platform.
27. **Additive schema migration** (section 9's "database migration must
    preserve data"): every stateful subsystem (memory, world model,
    audit log, policy/approval/credential engines, task engine, mandate/
    goal engines, guardian, enrollment) previously called a bare
    `Base.metadata.create_all(engine)` at startup, which only ever
    creates *missing tables* -- it silently does nothing to a table that
    already exists, so an owner upgrading to a version whose models
    added a column to an existing table would hit a real "no such
    column" error against their own already-populated database. Added
    `memory/schema_migration.py`'s `ensure_schema(engine)`, which still
    calls `create_all()` for brand-new tables but also inspects every
    already-existing table and adds any column present in the current
    model but missing on disk via SQLite's own `ALTER TABLE ... ADD
    COLUMN` -- never a table drop, never a rebuild, never touching an
    existing row. All 10 call sites switched over. Verified with a real
    intentionally-old on-disk schema built by hand with raw SQL (a
    stripped `audit_entries` table missing a column the current model
    has, with a real row inserted into it): after `ensure_schema()`, the
    old row survives with its real values intact, the new column exists
    and is queryable through the ORM, and a fresh row can be written
    through it normally. Also covers idempotency (safe to call twice)
    and the create-brand-new-table path. 3 new tests.
28. **"Run Gridkeep" without a generic goal-form** (section 10): added
    `parse_run_directive()` (`executive/directives.py`), an explicit
    regex match for "Run X" / "Operate X" -- never a guess at intent,
    matching this codebase's rule that anything driving a real decision
    either matches a known pattern or reports itself unrecognized. Wired
    into `MandateEngine.create_from_directive()`, `aura mandates run
    "Run Gridkeep"`, and `POST /mandates/run`: creates a draft mandate
    titled "Run Gridkeep" with mission "Operate and grow Gridkeep",
    scaffolded with the 13 standard operating departments (Executive,
    Sales, Marketing, Social Media, Customer Service, Customer Success,
    Operations, Production, Software Engineering, Finance, Security,
    Research, Growth) as its objectives -- a generic organizational
    scaffold, not a fabricated fact about any real business. The
    activation gate is deliberately untouched: KPIs and constraints for
    the *actual* business are still required, honestly, before
    `activate()` allows the mandate to run, since those are real facts
    about a real company this system has no way to know on its own. A
    directive-created mandate persists through a fresh `MandateEngine`
    against the same database_url, exactly like a process restart. 9 new
    tests (engine, CLI, API).
29. **"What's happening with Gridkeep?" answered from real state, in
    chat** (closing item 28's one remaining piece): `parse_status_query()`
    matches four explicit phrasings ("what's happening with X", "what's
    the status/update on/with X", "status/update on/for X", "how is X
    doing") -- never a guess, same discipline as `parse_run_directive()`.
    `MandateEngine.find_by_company()` does a plain substring match
    against every mandate's title/mission (most-recently-created match
    wins), regardless of status, so a mandate that was created but never
    activated is still found. Wired into `/chat` as a new deterministic
    lane (`"mandate_status"`) checked right after the existing exact-
    match trigger lookup and before the query ever reaches the model --
    a match renders the real `MandateReport` as text; no match answers
    honestly ("No mandate found matching 'X'") rather than falling
    through to a generic chatbot response, which is exactly the failure
    mode section 22 of the product brief warns against. 6 new tests (2
    directive-parsing/lookup unit tests, 2 through the real `/chat`
    endpoint, 2 more in the mandate-engine suite for `find_by_company`).
30. **Universal Capability Layer** (a general-purpose composition layer
    on top of the existing governance/connector/memory stack -- see
    `docs/UNIVERSAL_CAPABILITY_LAYER.md` for the full, honest scope
    statement, including what was deliberately not attempted and why):
    a `CapabilityRegistry` (`aura_core.capabilities`) cataloging 48
    real, already-registered action_types with domain/description/
    verification metadata, joined live against `ConnectorRegistry` and
    `RiskEngine` so availability and risk tier are always the real
    current state, never stale; a `SkillRegistry`/`SkillEngine`/
    `DynamicSkillBuilder` (`aura_core.skills`) letting AURA compose and
    permanently reuse named workflows out of *existing* capabilities
    only (every step still runs through the real Action Broker; an
    unknown capability name is rejected outright, never silently
    dropped) -- deliberately scoped away from generating or executing
    novel unreviewed code, a separate and much larger security
    undertaking; a `UniversalPlanner`/`parse_plan_response()`
    (`aura_core.planning`) that decomposes a free-text objective into
    real, currently-available capabilities via the Model Router,
    re-validating every proposed step against the live registry so a
    hallucinated capability name becomes a structured `CapabilityGap`
    (OBJECTIVE/MISSING_CAPABILITY/REQUIRED_TOOL/REQUIRED_PROVIDER/
    REQUIRED_PERMISSION/CAN_BUILD_SKILL/NEXT_ACTION) instead of a
    fabricated plan -- the same never-fabricate discipline
    `executive.parse_plan()` already applies to model output; an
    `OpportunityLedger` (`aura_core.opportunities`) for recording real
    opportunities/risks with evidence/confidence/impact/effort/next-
    action, deliberately without a detection engine (there is no real
    business data in a fresh instance to detect anything from yet --
    inventing pattern-matching against an empty World Model would be
    fabricated insight). CLI (`aura capabilities list`, `aura skills
    list|compose|run`, `aura plan`) and API (`GET /capabilities`, `GET|
    POST /skills`, `POST /skills/{id}/run`, `POST /plan`, `GET|POST
    /opportunities`, `POST /opportunities/{id}/status`) surfaces for
    all of it, gated like every other mutating endpoint. 30 new tests
    across the four new packages and their CLI/API wiring, plus a
    61-case capability evaluation harness (30 resolvable cases spanning
    every real domain in the catalog, 25 gap cases spanning sales,
    marketing, social strategy, customer support, coding/web
    development, design, active security testing, and plain model
    hallucination, 3 cross-domain objectives mixing resolved steps and
    gaps in one request) proving the resolve-or-report-a-gap mechanism
    generalizes, at a scale that's actually inspectable rather than
    padded to a round number.

Everything else in this audit marked `IMPLEMENTABLE_NOW` and not listed
above is real, tracked, remaining work — not hidden behind a blocker
label just because it hasn't been reached yet.
