namespace AuraVoice.Core;

/// <summary>
/// The real distinction between "muted" and "wake-word only" (voice-first
/// interface spec, section 17): FULL_MIC_OFF must physically stop audio
/// capture (see WindowsVoicePipeline, which stops the real NAudio device
/// when this gate reports <see cref="RequiresMicrophoneOff"/>);
/// WAKE_WORD_ONLY keeps the microphone open and wake-word detection
/// running — so the owner can still be heard starting a new session — but
/// blocks the transition into full command capture even if the wake word
/// fires. There is no state in which the assistant is "muted" yet still
/// executing commands.
///
/// Pure state, no audio I/O — fully unit-testable without a microphone,
/// the same principle VoiceSessionController already uses. The real
/// hardware-facing half (WindowsVoicePipeline, NAudioMicrophoneSource)
/// only ever asks this gate two yes/no questions and acts on the answer;
/// it never re-derives the privacy-mode logic itself.
/// </summary>
public enum VoicePrivacyMode
{
    Normal,
    WakeWordOnly,
    FullMicOff,
}

public sealed class VoicePrivacyGate
{
    public VoicePrivacyMode Mode { get; private set; } = VoicePrivacyMode.Normal;

    public event Action<VoicePrivacyMode>? ModeChanged;

    public void SetMode(VoicePrivacyMode mode)
    {
        if (Mode == mode)
        {
            return;
        }
        Mode = mode;
        ModeChanged?.Invoke(Mode);
    }

    /// <summary>True only for FullMicOff -- the one mode that must close
    /// the real hardware, not merely stop reacting to it.</summary>
    public bool RequiresMicrophoneOff => Mode == VoicePrivacyMode.FullMicOff;

    /// <summary>Whether a real wake-word detection happening right now
    /// should be allowed to proceed into full command capture. False for
    /// both restricted modes -- WakeWordOnly still runs the detector (so
    /// FullMicOff vs. WakeWordOnly is observably different to the owner:
    /// the mic indicator behaves differently), but a detection while
    /// restricted is discarded, never escalated to a real command.</summary>
    public bool AllowsWakeWordActivation => Mode == VoicePrivacyMode.Normal;
}
