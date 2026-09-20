using System.Speech.Synthesis;
using AuraVoice.Core;

namespace AuraVoice.Windows;

/// <summary>
/// Text-to-speech via Windows' built-in SAPI engine (System.Speech) — the
/// zero-extra-download, fully local default, consistent with the
/// project's local-first/private-first stance (docs/privacy/README.md).
/// Real code against the real System.Speech API — compiled successfully
/// in this session — but never run here: System.Speech.Synthesis is a
/// Windows-only wrapper over SAPI and cannot function on Linux regardless
/// of whether the assembly loads. See apps/voice/README.md.
/// </summary>
public sealed class SapiTextToSpeech : ITextToSpeech, IDisposable
{
    private readonly SpeechSynthesizer _synthesizer = new();

    public async Task SpeakAsync(string text, CancellationToken ct = default)
    {
        var completed = new TaskCompletionSource();

        void OnSpeakCompleted(object? sender, SpeakCompletedEventArgs e) => completed.TrySetResult();
        _synthesizer.SpeakCompleted += OnSpeakCompleted;

        using var registration = ct.Register(() =>
        {
            _synthesizer.SpeakAsyncCancelAll();
            completed.TrySetCanceled(ct);
        });

        try
        {
            _synthesizer.SpeakAsync(text);
            await completed.Task;
        }
        finally
        {
            _synthesizer.SpeakCompleted -= OnSpeakCompleted;
        }
    }

    public void Stop() => _synthesizer.SpeakAsyncCancelAll();

    public void Dispose() => _synthesizer.Dispose();
}
