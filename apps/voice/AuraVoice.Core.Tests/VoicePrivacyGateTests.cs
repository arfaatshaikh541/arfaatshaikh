using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

public class VoicePrivacyGateTests
{
    [Fact]
    public void Starts_in_normal_mode_allowing_wake_word_activation_without_requiring_the_mic_off()
    {
        var gate = new VoicePrivacyGate();

        Assert.Equal(VoicePrivacyMode.Normal, gate.Mode);
        Assert.True(gate.AllowsWakeWordActivation);
        Assert.False(gate.RequiresMicrophoneOff);
    }

    [Fact]
    public void FullMicOff_requires_the_real_hardware_closed_and_blocks_wake_word_activation()
    {
        var gate = new VoicePrivacyGate();

        gate.SetMode(VoicePrivacyMode.FullMicOff);

        Assert.True(gate.RequiresMicrophoneOff);
        Assert.False(gate.AllowsWakeWordActivation);
    }

    [Fact]
    public void WakeWordOnly_keeps_the_microphone_open_but_still_blocks_full_activation()
    {
        var gate = new VoicePrivacyGate();

        gate.SetMode(VoicePrivacyMode.WakeWordOnly);

        // This is the whole point of the distinction: WakeWordOnly is
        // observably different from FullMicOff (the mic keeps running),
        // but it must never let a wake-word detection escalate into a
        // real command the way Normal mode does.
        Assert.False(gate.RequiresMicrophoneOff);
        Assert.False(gate.AllowsWakeWordActivation);
    }

    [Fact]
    public void SetMode_fires_ModeChanged_only_for_a_real_transition()
    {
        var gate = new VoicePrivacyGate();
        var transitions = new List<VoicePrivacyMode>();
        gate.ModeChanged += transitions.Add;

        gate.SetMode(VoicePrivacyMode.Normal); // no-op, already Normal
        gate.SetMode(VoicePrivacyMode.WakeWordOnly);
        gate.SetMode(VoicePrivacyMode.WakeWordOnly); // no-op, unchanged
        gate.SetMode(VoicePrivacyMode.FullMicOff);
        gate.SetMode(VoicePrivacyMode.Normal);

        Assert.Equal(
            new[] { VoicePrivacyMode.WakeWordOnly, VoicePrivacyMode.FullMicOff, VoicePrivacyMode.Normal },
            transitions);
    }
}
