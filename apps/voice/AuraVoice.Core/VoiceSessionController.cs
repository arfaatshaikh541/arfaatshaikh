namespace AuraVoice.Core;

public enum VoiceState
{
    Idle,            // not listening at all ("close your ears")
    ListeningForWake, // always-listening for the wake phrase only
    Awake,            // wake phrase heard (or still within the post-response conversation window); capturing a command
    Processing,       // command captured, waiting for AURA's response
    Speaking,         // TTS is playing
}

/// <summary>
/// Pure state machine for the voice interaction loop — no audio I/O, no
/// model calls. This is deliberately separated from hardware/engine
/// concerns (mic capture, wake-word model, STT, TTS) so the actual
/// conversational logic — wake → listen → process → speak → (barge-in |
/// conversation window | sleep) — is fully testable without a microphone,
/// in this environment or any other. The audio-hardware harness (real,
/// Windows-only, unverified here — see apps/voice/README.md) is
/// responsible for calling these triggers in response to real events and
/// for actually starting/stopping capture and playback.
/// </summary>
public sealed class VoiceSessionController
{
    public VoiceState State { get; private set; } = VoiceState.Idle;

    public event Action<VoiceState>? StateChanged;
    public event Action? WakeWordDetected;
    public event Action<string>? CommandCaptured;
    public event Action? BargeInRequested;

    /// <summary>"AURA" / "wake up" — begin always-listening for the wake
    /// phrase. Idempotent from ListeningForWake; invalid mid-conversation
    /// (use Sleep() first, or let the flow reach ListeningForWake
    /// naturally via a conversation timeout).</summary>
    public void StartWakeListening()
    {
        if (State == VoiceState.ListeningForWake)
        {
            return; // already listening; not an error
        }

        RequireState(VoiceState.Idle, nameof(StartWakeListening));
        SetState(VoiceState.ListeningForWake);
    }

    /// <summary>"close your ears" — stop listening entirely, from any
    /// state. This is the one transition that is always legal, by
    /// design: the owner's request to stop must never be blocked by
    /// whatever AURA happens to be doing.</summary>
    public void Sleep()
    {
        SetState(VoiceState.Idle);
    }

    public void OnWakeWordDetected()
    {
        RequireState(VoiceState.ListeningForWake, nameof(OnWakeWordDetected));
        SetState(VoiceState.Awake);
        WakeWordDetected?.Invoke();
    }

    public void OnCommandCaptured(string text)
    {
        RequireState(VoiceState.Awake, nameof(OnCommandCaptured));
        SetState(VoiceState.Processing);
        CommandCaptured?.Invoke(text);
    }

    public void OnResponseReady()
    {
        RequireState(VoiceState.Processing, nameof(OnResponseReady));
        SetState(VoiceState.Speaking);
    }

    /// <summary>TTS playback finished normally. Returns to Awake, not
    /// ListeningForWake, so the owner can continue the conversation
    /// without repeating the wake phrase — the "conversation window"
    /// requirement. The caller's timer is responsible for calling
    /// OnConversationTimeout() if nothing follows within the window.</summary>
    public void OnSpeakingFinished()
    {
        RequireState(VoiceState.Speaking, nameof(OnSpeakingFinished));
        SetState(VoiceState.Awake);
    }

    /// <summary>The owner started talking while AURA was speaking. The
    /// caller must actually stop TTS playback (ITextToSpeech.Stop()) —
    /// this only updates the state and notifies listeners.</summary>
    public void OnBargeIn()
    {
        RequireState(VoiceState.Speaking, nameof(OnBargeIn));
        SetState(VoiceState.Awake);
        BargeInRequested?.Invoke();
    }

    /// <summary>No follow-up command within the post-response
    /// conversation window; return to wake-phrase-only listening.</summary>
    public void OnConversationTimeout()
    {
        RequireState(VoiceState.Awake, nameof(OnConversationTimeout));
        SetState(VoiceState.ListeningForWake);
    }

    private void RequireState(VoiceState required, string trigger)
    {
        if (State != required)
        {
            throw new InvalidOperationException(
                $"{trigger} is only valid from {required}, but current state is {State}.");
        }
    }

    private void SetState(VoiceState next)
    {
        if (State == next)
        {
            return;
        }
        State = next;
        StateChanged?.Invoke(State);
    }
}
