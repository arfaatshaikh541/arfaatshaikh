# AURA Real-Time Voice Layer

Split into three projects, each verified to the extent this environment
(a cloud Linux container, no audio hardware) genuinely allows:

| Project | Contains | Builds here? | Tested here? |
|---|---|---|---|
| `AuraVoice.Core` | VAD, the conversation state machine, engine interfaces | Yes | Yes — 11 tests, all passing |
| `AuraVoice.Windows` | Real NAudio microphone capture, the pipeline wiring it all together | Yes (net8.0-windows compiles on Linux without `UseWPF`) | No — needs a real microphone |
| `AuraVoice.Windows.Speech` | Real Windows SAPI text-to-speech (`System.Speech`) | Yes | No — needs Windows' speech engine at runtime |

## What's genuinely verified

```
cd AuraVoice.Core.Tests && dotnet test
```

**11 tests, all passing**, with zero mocking of the actual algorithms:

- `EnergyVoiceActivityDetector` correctly distinguishes silence from a
  real synthetic sine-wave "voice" signal at various amplitudes, using
  actual RMS-energy computation over real PCM16 sample arrays — not a
  stub that always returns a fixed answer.
- `VoiceSessionController` — the pure conversation state machine — is
  fully exercised: the happy path (wake → capture command → process →
  speak → conversation window → timeout back to wake-listening),
  barge-in during speech, "close your ears" (`Sleep()`) from any state
  including mid-conversation, "wake up" after sleep, idempotent
  re-entry into wake-listening, and illegal-transition rejection with a
  clear error message.

**All four projects also compile successfully** — `dotnet build` from
`apps/voice/` builds `AuraVoice.Core`, `AuraVoice.Core.Tests`,
`AuraVoice.Windows` (real NAudio mic-capture code, against NAudio's
actual API), and `AuraVoice.Windows.Speech` (real `System.Speech.
Synthesis.SpeechSynthesizer` code) with zero errors. This was not
assumed — it was tried, and one real bug was caught and fixed along
the way (see "Bugs found" below). Compiling is real signal: it proves
the code is syntactically and type-correct against the actual NAudio and
System.Speech APIs, not against a guess at their shape.

## What is NOT verified, and cannot be from here

Compiling is not running. None of the following has ever executed once
in this session, because there is no microphone, no speaker, and no
Windows speech engine available in this container:

- Actually capturing audio from a real microphone (`NAudioMicrophoneSource`).
- Actually producing audible speech (`SapiTextToSpeech`) — `System.Speech`
  is a thin wrapper over the Windows SAPI COM engine; it cannot function
  on Linux regardless of whether the .NET assembly loads.
- Whether the `EnergyVoiceActivityDetector`'s default threshold (500 on
  the 16-bit PCM scale) is remotely correct for a real microphone, room,
  and gain setting — it almost certainly needs tuning once real audio
  flows through it.
- Wake-word detection and speech-to-text are **not implemented at all**,
  only interfaced (`IWakeWordDetector`, `ISpeechToText` in
  `AuraVoice.Core/VoiceInterfaces.cs`), with `NullWakeWordDetector` /
  `NullSpeechToText` as the honest default (they never fire / they throw
  rather than silently returning an empty transcript). Wiring a real
  engine is future work — see "Next steps" below.
- End-to-end behavior of `WindowsVoicePipeline` (the class that wires mic
  capture → VAD → wake-word → utterance buffering → STT → the state
  machine → TTS together) has never run against real frames.

## Bugs found by actually trying to build

The `NAudio` umbrella NuGet package pulls in `NAudio.WinForms`, which
requires a `Microsoft.WindowsDesktop.App.WindowsForms` FrameworkReference
that fails to resolve on Linux — discovered by actually attempting the
build, not by inspecting the package first. Fixed by depending on
`NAudio.Core` + `NAudio.WinMM` directly (both plain `netstandard2.0`,
which is where `WaveInEvent` — the only NAudio type this project actually
uses — lives). A `.csproj` XML-comment containing `--` was also caught
by `dotnet sln add` refusing to parse the file, and fixed.

## Next steps to make this actually work on your machine

1. **Wake word**: the honest path is [Picovoice Porcupine](https://picovoice.ai/)
   — free tier available, needs your own `AccessKey` and a `.ppn` wake-word
   model file (Porcupine's console lets you train "AURA" as a custom
   wake word). Implement `IWakeWordDetector` against Porcupine's .NET
   SDK; nothing here can do this for you without that key.
2. **Speech-to-text**: [Vosk](https://alphacephei.com/vosk/) for a fully
   local/private option (download a model — a few hundred MB — and use
   its .NET binding), or route to a cloud STT API through the same
   Model-Privacy-Gateway discipline as `docs/privacy/README.md` if you'd
   rather not run a local model. Implement `ISpeechToText` against
   whichever you choose.
3. **Tune the VAD threshold and `SilenceFramesToEndUtterance`** in
   `WindowsVoicePipeline` against your actual microphone and room.
4. **Wire `WindowsVoicePipeline` into the WPF shell** (`apps/windows/`):
   on `CommandCaptured`, send the text to `AuraApiClient.ChatStreamAsync`
   (already real and tested) the same way `ChatViewModel.SendAsync` does;
   on receiving the full response, call `ITextToSpeech.SpeakAsync`, then
   `Controller.OnResponseReady()` / `OnSpeakingFinished()`.
5. Update `core/src/aura_core/status.py`'s `voice.wake_word`, `voice.stt`,
   `voice.tts` entries to `LIVE` **only** once each has been exercised for
   real on your machine — not when the code merely exists, consistent
   with every other capability status in this project.
