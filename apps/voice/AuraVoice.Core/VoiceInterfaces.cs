namespace AuraVoice.Core;

/// <summary>Detects a wake phrase (e.g. "AURA") in a stream of audio
/// frames. A real implementation (Porcupine, or an open on-device
/// keyword-spotting model) needs a trained/licensed model this codebase
/// does not bundle — see apps/voice/README.md. NullWakeWordDetector below
/// is the honest default: it never fires, so the system fails closed
/// (never falsely "wakes") rather than guessing.</summary>
public interface IWakeWordDetector
{
    bool ProcessFrame(ReadOnlySpan<short> frame);
}

public sealed class NullWakeWordDetector : IWakeWordDetector
{
    public bool ProcessFrame(ReadOnlySpan<short> frame) => false;
}

/// <summary>Converts captured audio to text. A real implementation (Vosk,
/// whisper.cpp, or a cloud STT API) is not wired in this codebase yet —
/// see apps/voice/README.md for the integration points and why.</summary>
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

/// <summary>Speaks text aloud. A real implementation (Windows SAPI via
/// System.Speech, or a cloud TTS API) is not wired in this codebase yet —
/// see apps/voice/README.md.</summary>
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
