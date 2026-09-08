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
/// Muting is UI-visible-only here: SetMuted flips what this control
/// displays, but does not, by itself, gate any actual audio capture —
/// that boundary lives in the real Windows audio host (see
/// docs/VOICE_FIRST_SECURE_INTERFACE.md for exactly what is and is not
/// wired up there). Never conflate "the shell shows Muted" with "the
/// microphone is closed."
/// </summary>
public sealed class VoiceModeViewModel : ObservableObject, IDisposable
{
    private readonly AuraApiClient _client;
    private readonly TimeSpan _reconnectDelay;
    private CancellationTokenSource? _cts;
    private Task? _observeTask;
    private VoiceVisualState _state = VoiceVisualState.Unknown;
    private bool _isMuted;

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
    /// UI-visible mute only (see class docs). WAKE-WORD-ONLY vs FULL MIC
    /// OFF is a distinction the real audio pipeline must enforce; this
    /// method has no way to reach into that pipeline from here.
    /// </summary>
    public void SetMuted(bool muted)
    {
        IsMuted = muted;
        State = muted ? VoiceVisualState.Muted : VoiceVisualState.Unknown;
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
