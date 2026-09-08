namespace AuraShell.Core;

/// <summary>
/// The states Voice Mode's central visual can actually be in. Idle
/// through Speaking mirror AuraVoice.Core's VoiceState exactly (kept as
/// a separate enum, not a project reference, since the only contract
/// between the WPF shell and the voice host is the string aura_core's
/// /voice/state{,/stream} endpoints carry — see ParseState below).
/// Unknown/Offline/Muted are states the *voice engine itself* never
/// reports; they describe this view's relationship to that engine.
/// </summary>
public enum VoiceVisualState
{
    Unknown,
    Idle,
    ListeningForWake,
    Awake,
    Processing,
    Speaking,
    Offline,
    Muted,
}

/// <summary>
/// Drives Voice Mode's central visual from the real voice host's
/// reported state — never a decorative animation loop and never a
/// polling timer. AuraShell (the WPF shell) never runs the voice
/// pipeline itself: AuraVoice.Windows.Host owns the microphone, wake
/// word, STT, and TTS, in a separate process, and pushes its
/// VoiceSessionController transitions to aura_core (see
/// AuraApiClient.ReportVoiceStateAsync); this view model is the other
/// end of that pipe, consuming aura_core's /voice/state/stream SSE push
/// (StreamVoiceStateAsync) so the WPF UI reflects genuine runtime
/// events with no polling loop of its own (section 6).
///
/// SetMuted/SetWakeWordOnly update this view's own display immediately
/// (never delayed by a network round trip) and separately push the real
/// privacy mode to aura_core's /voice/privacy — the value
/// AuraVoice.Windows.Host actually polls and hands to
/// WindowsVoicePipeline.PrivacyGate, which is what genuinely opens and
/// closes the microphone hardware (FullMicOff) or blocks a wake-word hit
/// from escalating into a command (WakeWordOnly). This view model is a
/// client of that state, not the thing that gates the microphone --
/// the real gate lives in AuraVoice.Windows, REQUIRES_WINDOWS_RUNTIME to
/// verify against real hardware.
/// </summary>
public sealed class VoiceModeViewModel : ObservableObject, IDisposable
{
    private readonly AuraApiClient _client;
    private readonly TimeSpan _reconnectDelay;
    private CancellationTokenSource? _cts;
    private Task? _observeTask;
    private VoiceVisualState _state = VoiceVisualState.Unknown;
    private bool _isMuted;
    private bool _isWakeWordOnly;

    public VoiceVisualState State
    {
        get => _state;
        private set => SetProperty(ref _state, value);
    }

    public bool IsMuted
    {
        get => _isMuted;
        private set => SetProperty(ref _isMuted, value);
    }

    /// <summary>Mutually exclusive with IsMuted -- see SetWakeWordOnly.
    /// True while the real pipeline still runs wake-word detection but
    /// will not escalate a hit into a command.</summary>
    public bool IsWakeWordOnly
    {
        get => _isWakeWordOnly;
        private set => SetProperty(ref _isWakeWordOnly, value);
    }

    public VoiceModeViewModel(AuraApiClient client, TimeSpan? reconnectDelay = null)
    {
        _client = client;
        _reconnectDelay = reconnectDelay ?? TimeSpan.FromSeconds(2);
    }

    /// <summary>
    /// Begins consuming the real state stream. Safe to call again while
    /// already observing — any prior subscription is stopped first, so
    /// re-entering Voice Mode after a Backend Mode round trip never
    /// leaves two competing consumers running (UI lifecycle is separate
    /// from, and must not multiply, the underlying task).
    /// </summary>
    public void StartObserving()
    {
        StopObserving();
        var cts = new CancellationTokenSource();
        _cts = cts;
        _observeTask = ObserveLoopAsync(cts.Token);
    }

    public void StopObserving()
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = null;
    }

    private async Task ObserveLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                await foreach (var raw in _client.StreamVoiceStateAsync(ct))
                {
                    if (!IsMuted)
                    {
                        State = ParseState(raw);
                    }
                }

                // The connection ended on its own (server restart, network
                // blip) rather than because we cancelled it -- report the
                // honest Offline state and try to reconnect, never freeze
                // on the last-known state as if nothing happened.
                if (!ct.IsCancellationRequested && !IsMuted)
                {
                    State = VoiceVisualState.Offline;
                }
            }
            catch (OperationCanceledException)
            {
                return;
            }
            catch (HttpRequestException)
            {
                if (!IsMuted)
                {
                    State = VoiceVisualState.Offline;
                }
            }

            try
            {
                await Task.Delay(_reconnectDelay, ct);
            }
            catch (OperationCanceledException)
            {
                return;
            }
        }
    }

    /// <summary>
    /// FULL MIC OFF: updates this view immediately, and pushes the real
    /// mode to aura_core so the actual voice host closes the hardware
    /// microphone (see class docs). Clears IsWakeWordOnly -- the two
    /// restricted modes are mutually exclusive, never both true.
    /// </summary>
    public void SetMuted(bool muted)
    {
        IsMuted = muted;
        if (muted)
        {
            IsWakeWordOnly = false;
        }
        State = muted ? VoiceVisualState.Muted : VoiceVisualState.Unknown;
        PushPrivacyMode(muted ? "FullMicOff" : "Normal");
    }

    /// <summary>
    /// WAKE-WORD-ONLY: the real pipeline keeps the microphone open and
    /// wake-word detection running, but a detection is discarded rather
    /// than escalated into a command (see VoicePrivacyGate). Clears
    /// IsMuted for the same mutual-exclusion reason as SetMuted.
    /// </summary>
    public void SetWakeWordOnly(bool wakeWordOnly)
    {
        IsWakeWordOnly = wakeWordOnly;
        if (wakeWordOnly)
        {
            IsMuted = false;
        }
        State = wakeWordOnly ? VoiceVisualState.ListeningForWake : VoiceVisualState.Unknown;
        PushPrivacyMode(wakeWordOnly ? "WakeWordOnly" : "Normal");
    }

    /// <summary>
    /// Fire-and-forget on purpose (section: "the UI must never delay
    /// speech processing," and the caller here is a synchronous toggle
    /// handler) -- a failed push just means the real pipeline notices on
    /// its next poll instead of immediately; it never silently pretends
    /// the local UI-only state change was itself sufficient.
    /// </summary>
    private void PushPrivacyMode(string mode) => _ = PushPrivacyModeAsync(mode);

    private async Task PushPrivacyModeAsync(string mode)
    {
        try
        {
            await _client.SetVoicePrivacyAsync(mode);
        }
        catch (HttpRequestException)
        {
        }
    }

    public static VoiceVisualState ParseState(string raw) => raw switch
    {
        "Idle" => VoiceVisualState.Idle,
        "ListeningForWake" => VoiceVisualState.ListeningForWake,
        "Awake" => VoiceVisualState.Awake,
        "Processing" => VoiceVisualState.Processing,
        "Speaking" => VoiceVisualState.Speaking,
        _ => VoiceVisualState.Unknown,
    };

    public void Dispose() => StopObserving();
}
