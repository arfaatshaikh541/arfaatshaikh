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

    /// <summary>Fires when the owner said a recognized shutdown phrase
    /// ("shut down", "power off", ...). The orchestrator itself only
    /// quiets the microphone (Controller.Sleep()) and speaks an
    /// acknowledgement -- ending the actual process is the host
    /// program's job, since only it knows how to shut down cleanly.</summary>
    public event Action? ShutdownRequested;

    private readonly Func<string, Func<string, Task>, CancellationToken, Task<string>>? _generateResponseStreaming;

    public ConversationOrchestrator(
        VoiceSessionController controller,
        Func<string, CancellationToken, Task<string>> generateResponse,
        ITextToSpeech textToSpeech,
        TimeSpan? conversationWindow = null,
        Func<TimeSpan, CancellationToken, Task>? delay = null,
        Func<string, Func<string, Task>, CancellationToken, Task<string>>? generateResponseStreaming = null)
    {
        _controller = controller;
        _generateResponse = generateResponse;
        _textToSpeech = textToSpeech;
        _conversationWindow = conversationWindow ?? TimeSpan.FromSeconds(8);
        _delay = delay ?? Task.Delay;
        _generateResponseStreaming = generateResponseStreaming;

        _controller.CommandCaptured += OnCommandCaptured;
        _controller.StateChanged += OnStateChanged;
    }

    private void OnCommandCaptured(string text)
    {
        var command = VoiceCommandPhrases.TryMatch(text);
        if (command is not null)
        {
            _ = HandleVoiceCommandAsync(command.Value);
            return;
        }
        _ = HandleCommandAsync(text);
    }

    /// <summary>"close your ears" / "stop listening" / "shut down" and
    /// their variants never reach the reasoning call at all -- they're
    /// owner-control phrases, not questions, and answering them as if
    /// they were prose would be exactly the "voice API demo, not an
    /// assistant" failure mode the product spec calls out by name.</summary>
    private async Task HandleVoiceCommandAsync(VoiceCommandPhrase command)
    {
        var acknowledgement = command == VoiceCommandPhrase.ShutDown
            ? "Shutting down."
            : "Okay, I'll stop listening.";

        _controller.OnResponseReady();
        await _textToSpeech.SpeakAsync(acknowledgement);

        // Sleep() has no state precondition (documented as "always legal,
        // by design") -- correct here too, since a barge-in during the
        // acknowledgement above may already have moved the controller to
        // Awake, and either way the owner's request to stop must win.
        _controller.Sleep();

        if (command == VoiceCommandPhrase.ShutDown)
        {
            ShutdownRequested?.Invoke();
        }

        ResponseSpoken?.Invoke(acknowledgement);
    }

    private async Task HandleCommandAsync(string text)
    {
        if (_generateResponseStreaming is not null)
        {
            await HandleCommandStreamingAsync(text);
            return;
        }

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

    /// <summary>Speaks each sentence of the reply as soon as it is
    /// available, rather than waiting for generation to finish -- the
    /// achievable approximation of "streaming TTS" this build supports
    /// (see SentenceSplitter's docstring for why true model-level audio
    /// streaming isn't available with the STT/TTS architectures in use).
    /// The first sentence transitions Processing -> Speaking exactly
    /// like the non-streaming path's single OnResponseReady() call; a
    /// barge-in mid-reply is honored immediately -- no further sentences
    /// are spoken once the controller has left the Speaking state.</summary>
    private async Task HandleCommandStreamingAsync(string text)
    {
        var spokenAnySentence = false;
        var response = string.Empty;

        async Task OnSentenceReady(string sentence)
        {
            if (_controller.State == VoiceState.Processing)
            {
                _controller.OnResponseReady();
            }
            else if (_controller.State != VoiceState.Speaking)
            {
                return; // interrupted (barge-in/sleep) before this sentence could be spoken
            }

            spokenAnySentence = true;
            await _textToSpeech.SpeakAsync(sentence);
        }

        try
        {
            response = await _generateResponseStreaming!(text, OnSentenceReady, CancellationToken.None);
        }
        catch (Exception ex)
        {
            ResponseFailed?.Invoke(ex);
        }

        // Nothing was ever spoken -- either the whole response failed
        // before producing any text, or it produced no text at all.
        // Falls back to the non-streaming path's exact behavior rather
        // than leaving the conversation stuck in Processing.
        if (!spokenAnySentence)
        {
            if (_controller.State == VoiceState.Processing)
            {
                _controller.OnResponseReady();
            }
            if (!string.IsNullOrEmpty(response) && _controller.State == VoiceState.Speaking)
            {
                await _textToSpeech.SpeakAsync(response);
            }
        }

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
