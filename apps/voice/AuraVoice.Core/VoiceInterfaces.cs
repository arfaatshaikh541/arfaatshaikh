namespace AuraVoice.Core;

/// <summary>Detects a wake phrase in a stream of audio frames. The real,
/// wired-in default is HttpWakeWordDetector (HttpProviders.cs), backed by
/// aura_core's /voice/wake-word/check endpoint — a genuine local
/// openWakeWord/ONNX model, no cloud dependency, no license key required.
/// NullWakeWordDetector below is the honest fallback for a caller with no
/// detector configured at all: it never fires, so the system fails closed
/// (never falsely "wakes") rather than guessing.</summary>
public interface IWakeWordDetector
{
    bool ProcessFrame(ReadOnlySpan<short> frame);
}

public sealed class NullWakeWordDetector : IWakeWordDetector
{
    public bool ProcessFrame(ReadOnlySpan<short> frame) => false;
}

/// <summary>Converts captured audio to text. The real, wired-in default is
/// HttpSpeechToText (HttpProviders.cs), backed by aura_core's
/// /voice/stt/transcribe endpoint — a genuine local sherpa-onnx
/// Whisper-tiny.en model, no cloud dependency.</summary>
public interface ISpeechToText
{
    Task<string> TranscribeAsync(ReadOnlyMemory<short> audio, int sampleRateHz, CancellationToken ct = default);
}

public sealed class NullSpeechToText : ISpeechToText
{
    public Task<string> TranscribeAsync(ReadOnlyMemory<short> audio, int sampleRateHz, CancellationToken ct = default) =>
        throw new NotSupportedException(
            "No speech-to-text engine is configured. See apps/voice/README.md to wire one in " +
            "(this is intentionally a hard failure, not a silent empty transcript).");
}

/// <summary>Speaks text aloud. Two real implementations exist: HttpTextToSpeech
/// (AuraVoice.Windows) — aura_core's /voice/tts/speak endpoint, a genuine
/// local sherpa-onnx/Piper voice, consistent across every machine AURA
/// runs on — and SapiTextToSpeech (AuraVoice.Windows.Speech) for Windows'
/// own built-in SAPI voice. AuraVoice.Windows.Host picks between them via
/// AURA_VOICE_TTS_ENGINE.</summary>
public interface ITextToSpeech
{
    Task SpeakAsync(string text, CancellationToken ct = default);

    /// <summary>Must stop audible output immediately — this is what
    /// makes barge-in/interruption actually silence AURA rather than
    /// letting it talk over the owner.</summary>
    void Stop();
}

public sealed class NullTextToSpeech : ITextToSpeech
{
    public Task SpeakAsync(string text, CancellationToken ct = default) =>
        throw new NotSupportedException(
            "No text-to-speech engine is configured. See apps/voice/README.md to wire one in.");

    public void Stop()
    {
        // Nothing is ever speaking via this engine, so there is nothing to stop.
    }
}
