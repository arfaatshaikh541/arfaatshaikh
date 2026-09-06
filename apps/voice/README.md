# AURA Real-Time Voice Layer

Five projects, each verified to the extent this environment (a cloud
Linux container, no audio hardware) genuinely allows:

| Project | Contains | Builds here? | Tested here? |
|---|---|---|---|
| `AuraVoice.Core` | VAD, the conversation state machine, `ConversationOrchestrator` (response generation + conversation-timeout glue), engine interfaces, the Http*-backed engine adapters | Yes | Yes — 21 tests, all passing |
| `AuraVoice.Windows` | Real NAudio microphone capture, `HttpTextToSpeech` (NAudio playback), the pipeline wiring it all together | Yes (net8.0-windows compiles on Linux without `UseWPF`) | No — needs a real microphone/speaker |
| `AuraVoice.Windows.Speech` | Real Windows SAPI text-to-speech (`System.Speech`) | Yes | No — needs Windows' speech engine at runtime |
| `AuraVoice.Windows.Host` | The composition root: an actual runnable console program wiring mic → VAD → wake-word → STT → aura_core reasoning → TTS → barge-in together | Yes | No — needs a real microphone |
| `AuraShell.Core` (in `apps/windows/`) | `AuraApiClient` (SSE `/chat` client), reused here rather than duplicated | Yes | Yes — see `apps/windows/README.md` |

## What's genuinely verified

```
cd AuraVoice.Core.Tests && dotnet test
```

**21 tests, all passing**, with zero mocking of the actual algorithms:

- `EnergyVoiceActivityDetector` correctly distinguishes silence from a
  real synthetic sine-wave "voice" signal at various amplitudes, using
  actual RMS-energy computation over real PCM16 sample arrays.
- `VoiceSessionController` — the pure conversation state machine — is
  fully exercised: the happy path (wake → capture command → process →
  speak → conversation window → timeout back to wake-listening),
  barge-in during speech, "close your ears" (`Sleep()`) from any state,
  "wake up" after sleep, idempotent re-entry into wake-listening, and
  illegal-transition rejection with a clear error message.
- `HttpWakeWordDetector` / `HttpSpeechToText` — fail closed (never
  falsely wake, never fabricate a transcript) when aura_core is
  unreachable, and correctly parse real JSON responses from a fake
  `HttpMessageHandler`.
- `ConversationOrchestrator` — the piece that turns a captured command
  into a spoken response — is exercised end to end: a command is
  answered and spoken, a failed response-generation call still returns
  the conversation to `Awake` instead of wedging it in `Processing`
  forever, a barge-in mid-speech is handled without an illegal
  double-transition, the conversation window genuinely times back out to
  wake-listening when nothing follows, and a genuine follow-up within
  the window correctly cancels the pending timeout.

**All five projects also compile successfully** — `dotnet build
AuraVoice.sln` builds every one of them, including `AuraVoice.Windows.Host`
(the actual runnable program) against `AuraShell.Core`'s real, tested
`AuraApiClient`. This was not assumed — it was tried, and real bugs were
caught and fixed along the way (see "Bugs found" below).

## The real, local voice providers behind this

Unlike an earlier draft of this codebase, wake-word detection and speech-
to-text are **not** placeholders here — no Porcupine account, no Vosk
download, no cloud API key required:

- **Wake word**: [openWakeWord](https://github.com/dscripka/openWakeWord)
  running its ONNX backend against a real `hey_jarvis` model, served by
  aura_core's `/voice/wake-word/check` endpoint
  (`core/src/aura_core/voice/wake_word.py`). `HttpWakeWordDetector`
  (`AuraVoice.Core/HttpProviders.cs`) is the C# side of that call.
- **Speech-to-text**: [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
  running a real Whisper-tiny.en ONNX model, served by
  `/voice/stt/transcribe` (`core/src/aura_core/voice/stt.py`).
  `HttpSpeechToText` is the C# side.
- **Text-to-speech**: sherpa-onnx again, this time a Piper/VITS ONNX
  voice, served by `/voice/tts/speak` (`core/src/aura_core/voice/tts.py`).
  `HttpTextToSpeech` (`AuraVoice.Windows/HttpTextToSpeech.cs`) plays the
  returned WAV via NAudio. `SapiTextToSpeech`
  (`AuraVoice.Windows.Speech/SapiTextToSpeech.cs`) is the alternative —
  Windows' own built-in SAPI voice, zero extra download. `AuraVoice.
  Windows.Host` picks between them with `AURA_VOICE_TTS_ENGINE=local|sapi`.

All three models were genuinely downloaded (from GitHub releases — the
only reachable large-file host from this sandbox's network policy) and
exercised with real inference in this session — see
`core/src/aura_core/voice/` and its tests for the Python-side proof.
`aura_core/RUNBOOK.md` explains how to get the same model files onto
your machine.

This is exactly the provider-abstraction shape the product brief asked
for: `IWakeWordDetector` / `ISpeechToText` / `ITextToSpeech` are the
seams, the Http* classes are today's local-first, no-cloud-dependency
implementation, and a Porcupine- or cloud-STT-backed alternative could be
added later as another implementation of the same interface without
touching `WindowsVoicePipeline`, `ConversationOrchestrator`, or the state
machine at all.

## Running the actual assistant

```
cd AuraVoice.Windows.Host
AURA_CORE_URL=http://127.0.0.1:8000 dotnet run
```

This is the real, wired-together pipeline described in the product
brief: microphone → VAD → wake-word → streaming STT → aura_core
reasoning/action (via the same `AuraApiClient.ChatStreamAsync` the WPF
shell uses) → TTS → barge-in. It has never been run against real audio in
this session (no microphone/speaker here) — see "What is NOT verified"
below — but it is genuinely structurally complete: no interface is left
as a `NullXxx` placeholder in this composition root, and it compiles
cleanly against the real NAudio, System.Speech, and aura_core-HTTP APIs.

Environment variables:
- `AURA_CORE_URL` — where aura_core's API is running (default `http://127.0.0.1:8000`).
- `AURA_VOICE_TTS_ENGINE` — `local` (default, sherpa-onnx/Piper via aura_core) or `sapi` (Windows SAPI).
- `AURA_VOICE_CONVERSATION_WINDOW_SECONDS` — how long AURA keeps listening after speaking before requiring the wake phrase again (default 8).

## What is NOT verified, and cannot be from here

Compiling and unit-testing the pure logic is not the same as running
against real hardware. None of the following has ever executed once in
this session, because there is no microphone, no speaker, and no Windows
speech engine available in this container:

- Actually capturing audio from a real microphone (`NAudioMicrophoneSource`).
- Actually producing audible speech (`SapiTextToSpeech`, and the NAudio
  playback side of `HttpTextToSpeech`).
- Whether `EnergyVoiceActivityDetector`'s default threshold (500 on the
  16-bit PCM scale) is correct for a real microphone, room, and gain
  setting — it almost certainly needs tuning once real audio flows
  through it.
- Whether openWakeWord's `hey_jarvis` model (the only wake word bundled
  so far — training a custom "AURA" wake word is future work, see
  openWakeWord's training docs) and the Whisper-tiny.en STT model perform
  acceptably against a real microphone's noise floor and a real room,
  as opposed to the clean bundled test WAVs they were verified against in
  `core/tests/test_voice_*.py`.
- Round-trip latency of `HttpWakeWordDetector.ProcessFrame` (one HTTP
  call per audio frame, synchronous by interface contract) — a real
  optimization candidate once this runs against real audio and the
  actual latency is measured, not before.
- End-to-end behavior of `WindowsVoicePipeline` and
  `AuraVoice.Windows.Host` against real frames, a real aura_core server,
  and real playback hardware.

`WINDOWS-COMMISSIONING.ps1` at the repo root runs the hardware-dependent
checks this environment cannot: wake word, STT, TTS, and barge-in against
real audio, once you have a Windows machine to run it on.

## Bugs found by actually trying to build and test

- The `NAudio` umbrella NuGet package pulls in `NAudio.WinForms`, which
  requires a `Microsoft.WindowsDesktop.App.WindowsForms` FrameworkReference
  that fails to resolve on Linux. Fixed by depending on `NAudio.Core` +
  `NAudio.WinMM` directly (both plain `netstandard2.0`, which is where
  `WaveInEvent`/`WaveOutEvent` — the only NAudio types actually used here —
  live).
- `.csproj` XML comments containing `--` broke `dotnet sln add`'s XML
  parser more than once across this codebase's history — worth remembering
  before writing a comment with an em-dash-style `--` separator in any
  `.csproj`.
- `HttpWakeWordDetector.ProcessFrame` originally only checked
  `IsSuccessStatusCode`, not `HttpRequestException` — meaning "aura_core
  is unreachable" threw instead of failing closed. Fixed to catch it and
  return `false`.
- A `ConversationOrchestrator` test that asserted the controller's state
  immediately after `OnCommandCaptured` was flawed: `HandleCommandAsync`
  runs fire-and-forget, and when `generateResponse` resolves
  synchronously (as it does in that test), execution can race straight
  through `Processing` to `Speaking` before the triggering call even
  returns. Fixed by removing the premature assertion rather than the
  (correct) production code.
- A `FakeTextToSpeech` test double initially resolved its `SpeakAsync`
  task's continuations synchronously from within `Stop()` — unlike a real
  playback API (NAudio's `WaveOutEvent`), which always completes later,
  off a separate callback. That mismatch could have hidden a real
  ordering bug in `ConversationOrchestrator`'s barge-in handling. Fixed by
  constructing the fake's `TaskCompletionSource` with
  `RunContinuationsAsynchronously`.

## Next steps for real hardware validation

1. Run `WINDOWS-COMMISSIONING.ps1` on your Windows machine — it exercises
   microphone capture, VAD, wake word, STT, TTS, and barge-in against
   real audio, and produces one diagnostic bundle if anything fails.
2. Tune `EnergyVoiceActivityDetector`'s threshold and
   `WindowsVoicePipeline.SilenceFramesToEndUtterance` against your actual
   microphone and room.
3. Optionally train a custom "AURA" wake word with openWakeWord (its
   training notebook needs a few minutes of synthetic/real audio) instead
   of the bundled `hey_jarvis` model, and point `AURA_WAKEWORD_MODEL` at it.
4. Update `core/src/aura_core/status.py`'s `voice.wake_word`, `voice.stt`,
   `voice.tts` entries to `LIVE` once each has been exercised for real
   on your machine — not when the code merely exists, consistent with
   every other capability status in this project.
