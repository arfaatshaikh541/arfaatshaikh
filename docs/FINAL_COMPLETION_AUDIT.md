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
| World Model (entities/relationships) | Yes | Partially — `WorldModelStore` exists on `Runtime` but nothing writes to it automatically; only reachable via direct method calls | Real | Yes | No | Nothing populates it from observation; no connector/executive code calls `upsert_entity`/`link` | `IMPLEMENTABLE_NOW` |
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
| Security Guardian | Yes | Yes (`on_audit` hook wired in `runtime.py`) | Real | Yes | No | Independent of the Action Broker, but still in-process — a compromised core process could theoretically disable both together; a truly separate watchdog process is future work | `IMPLEMENTABLE_NOW` (out-of-process guardian) — not done this pass, flagged |
| Credential Broker | Yes | Yes | **Bookkeeping only** — issues opaque scoped tokens, never a real secret. Real secrets (SMTP password, future API keys) live in plain environment variables today, no encryption at rest, no OS credential-store integration | Yes | No | Real secret vault backed by Windows Credential Manager/DPAPI | `REQUIRES_WINDOWS_RUNTIME` (DPAPI is Windows-only; code can be written and unit-tested with a mock store here, but real DPAPI encryption can't be exercised in this Linux sandbox) |
| Rate Limiter | Yes | Yes | Real | Yes | No | None found | `COMPLETE` |
| Audit Log (hash-chained) | Yes | Yes | Real | Yes | No | None found | `COMPLETE` |
| Owner enrollment / device trust | **No** | — | — | — | — | Entire capability: first-run identity creation, trusted-device marker, "don't re-authenticate every launch" | `IMPLEMENTABLE_NOW` for the local-identity/session-token mechanism; `REQUIRES_WINDOWS_RUNTIME` for DPAPI-backed secret storage specifically |

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
| "close your ears" / "stop listening" / "shut down" commands | Partial | `VoiceSessionController.Sleep()` exists and is tested | Real | Yes | No | Nothing routes a recognized phrase like "close your ears" to `Sleep()` — STT output goes straight to the reasoning call, not to a command-phrase check first | `IMPLEMENTABLE_NOW` — built this pass |
| Process supervision / crash recovery | Yes (`aura voice run` via `Supervisor`) | Yes | Real | Yes | No | None found | `COMPLETE` (for process-level recovery; acoustic/device recovery is `REQUIRES_PHYSICAL_DEVICE`) |

## E. Browser / Computer control

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Browser automation | Yes | Yes | Real Playwright | Yes | Partial (Linux Chromium; not the Windows browser binary) | CAPTCHA detection/escalation, persistent authenticated profiles, multi-tab/download handling | `IMPLEMENTABLE_NOW` — CAPTCHA detection added this pass; persistent profiles/multi-tab not done this pass, flagged |
| Desktop control | Yes | Yes | Real `pynput` | Yes (Xvfb) | No | Blind coordinate clicks only — no UI Automation/accessibility-tree targeting (section 16 explicitly asks to prefer this) | `REQUIRES_WINDOWS_RUNTIME` — UI Automation is a Windows API (`System.Windows.Automation`), can't be exercised here; interface can be added now |

## F. Installation

| Capability | Exists | Wired end-to-end | Real or mock | Tested | Windows validated | Missing work | Blocker |
|---|---|---|---|---|---|---|---|
| Preflight checker | Yes | Yes | Real | Yes | Confirmed working by the owner's own commissioning run | None found | `COMPLETE` |
| Staged install + rollback | Yes (`Install-AURA.ps1`) | Written | Real logic | No (never executed — no `pwsh` in this sandbox until this session found a workaround) | No | Never run end-to-end even once | `REQUIRES_WINDOWS_RUNTIME` |
| Single packaged installer (`.exe`/MSI) | **No** | — | — | — | — | Everything in section 10 — this is a PowerShell script, not an installer artifact | `REQUIRES_WINDOWS_RUNTIME` for the actual packaging step (WiX/Inno Setup need a Windows toolchain or a cross-compiler this sandbox doesn't have network access to verify); the *script logic* WiX would wrap is `IMPLEMENTABLE_NOW` and unchanged this pass |
| Upgrade preserving identity/memory/secrets | Partial (`Install-AURA.ps1` copies forward the DB and `.models/`) | Written, untested | Real logic | No | No | Never verified with real prior-version state | `REQUIRES_WINDOWS_RUNTIME` |
| Automatic repair (health supervision beyond process restart) | Partial (`Supervisor` = process restart only) | Yes for what it does | Real | Yes | No | Stale-lease repair, corrupted-cache repair, orphan-process detection, staged-upgrade rollback trigger | `IMPLEMENTABLE_NOW` — not done this pass, flagged (large scope) |

## G. Connectors — real status, not aspirational

| Connector | Exists | Wired | Real or mock | Tested | Live authenticated account | Blocker |
|---|---|---|---|---|---|---|
| Filesystem | Yes | Yes | Real | Yes | N/A (local) | `COMPLETE` |
| HTTP (generic egress) | Yes | Yes | Real | Yes | N/A | `COMPLETE` |
| Desktop control | Yes | Yes | Real | Yes | N/A | See section E above |
| Browser | Yes | Yes | Real | Yes | N/A | See section E above |
| Telephony | Yes | Yes | **MOCK, correctly labeled** (`MockTelephonyProvider`) | Yes | No | `REQUIRES_EXTERNAL_PROVIDER` (must pick Twilio/SIP first) + `REQUIRES_OWNER_CREDENTIAL` |
| Email (SMTP send) | Yes | Yes | Real SMTP client, tested against a real local server | Yes | No (needs owner's real SMTP account) | `REQUIRES_OWNER_CREDENTIAL` |
| Email (IMAP receive, threading, classify, drafts) | **No** | — | — | — | Entire capability from section 12 | `IMPLEMENTABLE_NOW` for IMAP receive/threading itself; classify/intent needs the model router (already available) |
| Generic REST/CRM connector | Yes | Yes | Real HTTP client against a configurable capability map | Yes | No | This is correctly an abstraction, not an integration — the spec is right that "a generic REST connector existing" does not mean a CRM integration exists. No concrete CRM adapter (HubSpot/Salesforce/Zoho schema mapping) exists. | `REQUIRES_EXTERNAL_PROVIDER` for which CRM; `REQUIRES_OWNER_CREDENTIAL` for its API key |
| Finance | Yes | Not auto-registered (by design) | **MOCK, correctly labeled** (`MockPaymentProvider`, drafts only) | Yes | No | `REQUIRES_EXTERNAL_PROVIDER` + `REQUIRES_OWNER_CREDENTIAL`, and `INTENTIONALLY_PROHIBITED` for autonomous execution specifically (per section 27) |
| Meta/Instagram | **No** | — | — | — | — | Entire capability. Building the OAuth flow, webhook handler, and Graph API adapter is `IMPLEMENTABLE_NOW` for the code; the live account test is `REQUIRES_OWNER_AUTHORIZATION` + `REQUIRES_PLATFORM_APPROVAL` (Meta app review for several permissions) |
| WhatsApp Business | **No** | — | — | — | — | Same shape as Meta: adapter code `IMPLEMENTABLE_NOW`, live test `REQUIRES_OWNER_CREDENTIAL` (a WhatsApp Business phone number) + `REQUIRES_EXTERNAL_PROVIDER` |
| LinkedIn | **No** | — | — | — | — | LinkedIn's current public API surface for a personal/company page is narrow (no general posting API without partner approval). Adapter for what's legitimately available is `IMPLEMENTABLE_NOW`; anything beyond that is `REQUIRES_PLATFORM_APPROVAL` |
| Git/software workflow (repos, PRs, issues, CI status) | **No dedicated connector** — this session used GitHub's MCP tools directly, not an AURA connector | — | — | — | — | `IMPLEMENTABLE_NOW` — not done this pass (large scope on its own), flagged |
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
| Endurance (`tests/endurance/`) | **Did not exist before this pass** |
| Synthetic long-memory validation | **Did not exist before this pass** |
| Windows acceptance harness | `WINDOWS-COMMISSIONING.ps1` exists and was run once for real by the owner (5 PASS / 7 FAIL / 6 SKIP, failures traced to environment setup issues, not code — see conversation history) |

---

## What this pass actually builds (see commits following this document)

Given the scope of the full specification is a multi-month, multi-person
production system, this pass prioritizes the single highest-leverage,
fully-buildable-without-Windows-or-credentials item the spec itself
names as the biggest gap: **the persistent operating loop and Mandate
model** (PHASE 4), plus the smaller `IMPLEMENTABLE_NOW` items that
support or are directly required by it (goal→mandate migration, a real
worker loop, executive-grade status reporting, voice command-phrase
routing, browser CAPTCHA detection). Everything else in this audit
marked `IMPLEMENTABLE_NOW` and not called out as "done this pass" is
real, tracked, remaining work — not being hidden behind a blocker
label.
