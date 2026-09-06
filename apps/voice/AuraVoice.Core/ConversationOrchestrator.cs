namespace AuraVoice.Core;

/// <summary>
/// Wires VoiceSessionController's pure state machine to the two things it
/// cannot know about itself: how to turn captured text into a spoken
/// response, and how long to wait for a follow-up before falling back to
/// wake-phrase-only listening. This is the piece that turns "a tested
/// state machine" and "tested engine adapters" into an actual working
/// conversational loop -- generateResponse and textToSpeech are injected
/// so this class has no dependency on HTTP, aura_core's API shape, or any
/// platform audio API, and so its own timing/ordering logic (including the
/// barge-in race against a response that's still being generated or
/// spoken) is fully unit-testable without a network or a microphone.
/// </summary>
public sealed class ConversationOrchestrator : IDisposable
{
    private readonly VoiceSessionController _controller;
    private readonly Func<string, CancellationToken, Task<string>> _generateResponse;
    private readonly ITextToSpeech _textToSpeech;
    private readonly TimeSpan _conversationWindow;
    private readonly Func<TimeSpan, CancellationToken, Task> _delay;
    private CancellationTokenSource? _timeoutCts;

    /// <summary>Fires once a response has been generated and spoken (or
    /// generation failed and there was nothing to speak) -- useful for
    /// logging/diagnostics; the state machine has already moved on by the
    /// time this fires.</summary>
    public event Action<string>? ResponseSpoken;

    /// <summary>Fires if generateResponse throws. The conversation still
    /// continues (AURA just has nothing to say), consistent with this
    /// project's "fail closed on trust decisions, fail visibly-but-
    /// gracefully on everything else" discipline -- a broken reasoning
    /// call must never wedge the voice loop in Processing forever.</summary>
    public event Action<Exception>? ResponseFailed;

    public ConversationOrchestrator(
        VoiceSessionController controller,
        Func<string, CancellationToken, Task<string>> generateResponse,
        ITextToSpeech textToSpeech,
        TimeSpan? conversationWindow = null,
        Func<TimeSpan, CancellationToken, Task>? delay = null)
    {
        _controller = controller;
        _generateResponse = generateResponse;
        _textToSpeech = textToSpeech;
        _conversationWindow = conversationWindow ?? TimeSpan.FromSeconds(8);
        _delay = delay ?? Task.Delay;

        _controller.CommandCaptured += OnCommandCaptured;
        _controller.StateChanged += OnStateChanged;
    }

    private void OnCommandCaptured(string text)
    {
        _ = HandleCommandAsync(text);
    }

    private async Task HandleCommandAsync(string text)
    {
        var response = string.Empty;
        try
        {
            response = await _generateResponse(text, CancellationToken.None);
        }
        catch (Exception ex)
        {
            ResponseFailed?.Invoke(ex);
        }

        _controller.OnResponseReady();
        if (!string.IsNullOrEmpty(response))
        {
            await _textToSpeech.SpeakAsync(response);
        }

        // A barge-in during the awaited SpeakAsync() call above already
        // moved the controller back to Awake (and stopped playback) --
        // calling OnSpeakingFinished() again here would be an illegal
        // transition, so only complete normally if nothing interrupted us.
        if (_controller.State == VoiceState.Speaking)
        {
            _controller.OnSpeakingFinished();
        }

        ResponseSpoken?.Invoke(response);
    }

    private void OnStateChanged(VoiceState state)
    {
        if (state == VoiceState.Awake)
        {
            ScheduleConversationTimeout();
        }
        else
        {
            CancelConversationTimeout();
        }
    }

    private void ScheduleConversationTimeout()
    {
        CancelConversationTimeout();
        var cts = new CancellationTokenSource();
        _timeoutCts = cts;
        _ = RunTimeoutAsync(cts);
    }

    private async Task RunTimeoutAsync(CancellationTokenSource cts)
    {
        try
        {
            await _delay(_conversationWindow, cts.Token);
        }
        catch (OperationCanceledException)
        {
            return;
        }

        // Re-check state: by the time the delay elapsed, a new command may
        // already have moved us out of Awake through some path that didn't
        // go through CancelConversationTimeout (there shouldn't be one,
        // but re-checking costs nothing and keeps this robust).
        if (!cts.IsCancellationRequested && _controller.State == VoiceState.Awake)
        {
            _controller.OnConversationTimeout();
        }
    }

    private void CancelConversationTimeout()
    {
        _timeoutCts?.Cancel();
        _timeoutCts = null;
    }

    public void Dispose()
    {
        CancelConversationTimeout();
        _controller.CommandCaptured -= OnCommandCaptured;
        _controller.StateChanged -= OnStateChanged;
    }
}
