using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

public class VoiceActivityDetectorTests
{
    private static short[] Silence(int length) => new short[length]; // all zeros

    private static short[] ToneAt(double amplitude, int length)
    {
        var samples = new short[length];
        for (var i = 0; i < length; i++)
        {
            // A real sine tone, not a constant DC value -- exercises the
            // RMS computation the way real audio actually would, rather
            // than testing a degenerate case.
            samples[i] = (short)(amplitude * Math.Sin(2 * Math.PI * 440 * i / 16000.0));
        }
        return samples;
    }

    [Fact]
    public void Silence_is_not_speech()
    {
        var vad = new EnergyVoiceActivityDetector(rmsThreshold: 500);
        Assert.False(vad.IsSpeech(Silence(320)));
    }

    [Fact]
    public void Loud_tone_above_threshold_is_speech()
    {
        var vad = new EnergyVoiceActivityDetector(rmsThreshold: 500);
        Assert.True(vad.IsSpeech(ToneAt(amplitude: 10000, length: 320)));
    }

    [Fact]
    public void Quiet_tone_below_threshold_is_not_speech()
    {
        var vad = new EnergyVoiceActivityDetector(rmsThreshold: 5000);
        Assert.False(vad.IsSpeech(ToneAt(amplitude: 100, length: 320)));
    }

    [Fact]
    public void Empty_frame_is_never_speech()
    {
        var vad = new EnergyVoiceActivityDetector();
        Assert.False(vad.IsSpeech(ReadOnlySpan<short>.Empty));
    }

    [Fact]
    public void Threshold_must_be_positive()
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => new EnergyVoiceActivityDetector(rmsThreshold: 0));
        Assert.Throws<ArgumentOutOfRangeException>(() => new EnergyVoiceActivityDetector(rmsThreshold: -1));
    }
}
