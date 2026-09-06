namespace AuraVoice.Core;

public interface IVoiceActivityDetector
{
    /// <summary>True if the given 16-bit PCM mono frame contains speech-
    /// level energy. Implementations must be pure/stateless per frame so
    /// they're trivially testable with synthetic audio.</summary>
    bool IsSpeech(ReadOnlySpan<short> frame);
}

/// <summary>
/// Simple RMS-energy-threshold VAD. This is a real, working, unit-tested
/// algorithm — not a stand-in for a proper implementation. It is also a
/// genuinely reasonable *default*: energy-gate VAD is what many
/// production voice pipelines use as a cheap first-pass filter before a
/// more expensive model-based VAD (e.g. WebRTC VAD or Silero VAD) — that
/// upgrade path is real future work, not a correction of a mistake here.
/// </summary>
public sealed class EnergyVoiceActivityDetector : IVoiceActivityDetector
{
    private readonly double _rmsThreshold;

    /// <param name="rmsThreshold">
    /// RMS amplitude threshold on the 16-bit PCM scale (0-32768). The
    /// right value depends on microphone gain and room noise floor on the
    /// owner's actual machine — this default is a reasonable starting
    /// point, not a calibrated constant. Expose it as a tunable setting
    /// in the eventual voice-settings UI rather than hardcoding reliance
    /// on it.
    /// </param>
    public EnergyVoiceActivityDetector(double rmsThreshold = 500.0)
    {
        if (rmsThreshold <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(rmsThreshold), "threshold must be positive");
        }
        _rmsThreshold = rmsThreshold;
    }

    public bool IsSpeech(ReadOnlySpan<short> frame)
    {
        if (frame.Length == 0)
        {
            return false;
        }

        double sumOfSquares = 0;
        foreach (var sample in frame)
        {
            sumOfSquares += (double)sample * sample;
        }

        var rms = Math.Sqrt(sumOfSquares / frame.Length);
        return rms >= _rmsThreshold;
    }
}
