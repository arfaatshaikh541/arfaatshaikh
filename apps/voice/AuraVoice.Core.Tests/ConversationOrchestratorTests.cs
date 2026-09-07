using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

public class ConversationOrchestratorTests
{
    private sealed class FakeTextToSpeech : ITextToSpeech
    {
        public List<string> Spoken { get; } = new();
        public int StopCount { get; private set; }
        private TaskCompletionSource? _pending;

        public Task SpeakAsync(string text, CancellationToken ct = default)
        {
            Spoken.Add(text);
            // RunContinuationsAsynchronously matters here: a real playback
            // API (NAudio) never resolves the awaited task synchronously
            // from within Stop() -- it always completes later, off a
            // separate callback. Matching that means Stop() -> OnBargeIn()
            // ordering in the test behaves the same as it does in
            // WindowsVoicePipeline.OnFrameCaptured against real hardware.
            _pending = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            return _pending.Task;
        }

        /// <summary>Lets a test finish a SpeakAsync call it's currently
        /// awaiting, simulating real playback ending.</summary>
        public void FinishSpeaking() => _pending?.TrySetResult();

        public void Stop()
        {
            StopCount++;
            _pending?.TrySetResult(); // real ITextToSpeech implementations end the SpeakAsync() await on Stop()
        }
    }

    private static Func<TimeSpan, CancellationToken, Task> ShortDelay(int milliseconds = 5) =>
        (_, ct) => Task.Delay(milliseconds, ct);

    private static Func<TimeSpan, CancellationToken, Task> NeverFires() =>
        (_, ct) => Task.Delay(Timeout.Infinite, ct);

    [Fact]
    public async Task Captured_command_is_answered_and_spoken_then_returns_to_awake()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (text, _) => Task.FromResult($"echo: {text}"), tts, delay: NeverFires());

        var spoken = new TaskCompletionSource<string>();
        orchestrator.ResponseSpoken += text => spoken.TrySetResult(text);

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("what's on my calendar");
        // Note: no assertion on State immediately here -- HandleCommandAsync
        // is fire-and-forget, and since generateResponse resolves
        // synchronously in this test, it can race straight through
        // Processing to Speaking before this line even returns.

        // HandleCommandAsync runs on a fire-and-forget background task, so
        // wait for it to actually reach SpeakAsync() before resolving the
        // fake playback -- calling FinishSpeaking() too early would signal
        // a TaskCompletionSource that gets replaced by the real call.
        await WaitUntil(() => tts.Spoken.Count == 1);
        tts.FinishSpeaking();
        var result = await spoken.Task.WaitAsync(TimeSpan.FromSeconds(2));

        Assert.Equal("echo: what's on my calendar", result);
        Assert.Single(tts.Spoken);
        Assert.Equal(VoiceState.Awake, controller.State);
    }

    [Fact]
    public async Task A_failed_response_generation_still_returns_the_conversation_to_awake()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (_, _) => throw new InvalidOperationException("model unreachable"), tts, delay: NeverFires());

        Exception? failure = null;
        var failed = new TaskCompletionSource();
        orchestrator.ResponseFailed += ex => { failure = ex; failed.TrySetResult(); };

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("do something");

        await failed.Task.WaitAsync(TimeSpan.FromSeconds(2));

        Assert.IsType<InvalidOperationException>(failure);
        Assert.Empty(tts.Spoken); // nothing to speak -- and critically, no exception escaped
        Assert.Equal(VoiceState.Awake, controller.State); // never stuck in Processing
    }

    [Fact]
    public async Task Barge_in_during_playback_does_not_double_transition_and_stops_the_conversation_cleanly()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (text, _) => Task.FromResult("a long response"), tts, delay: NeverFires());

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("tell me a long story");

        // Give HandleCommandAsync a moment to reach Speaking (OnResponseReady + SpeakAsync call).
        await WaitUntil(() => controller.State == VoiceState.Speaking);

        // Simulate what WindowsVoicePipeline does on real barge-in: stop
        // playback (which resolves the pending SpeakAsync await) and tell
        // the controller directly.
        tts.Stop();
        controller.OnBargeIn();

        // The orchestrator's HandleCommandAsync wakes up from the now-
        // completed SpeakAsync task; it must see State != Speaking and
        // must NOT call OnSpeakingFinished() again (which would throw).
        await WaitUntil(() => controller.State == VoiceState.Awake);
        Assert.Equal(1, tts.StopCount);
    }

    [Fact]
    public async Task Conversation_window_times_out_back_to_wake_listening_when_nothing_follows()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (text, _) => Task.FromResult("ok"), tts, delay: ShortDelay());

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("do the thing");
        await WaitUntil(() => tts.Spoken.Count == 1);
        tts.FinishSpeaking();

        await WaitUntil(() => controller.State == VoiceState.ListeningForWake, timeoutMs: 3000);
    }

    [Fact]
    public async Task A_follow_up_command_within_the_window_cancels_the_pending_timeout()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        var callCount = 0;
        using var orchestrator = new ConversationOrchestrator(
            controller,
            (text, _) => { callCount++; return Task.FromResult("ok"); },
            tts,
            delay: NeverFires());

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("first command");
        await WaitUntil(() => tts.Spoken.Count == 1);
        tts.FinishSpeaking();
        await WaitUntil(() => controller.State == VoiceState.Awake);

        // Still Awake (NeverFires means the timeout can't have silently
        // fired); a genuine follow-up must still be accepted.
        controller.OnCommandCaptured("second command");
        await WaitUntil(() => tts.Spoken.Count == 2);
        tts.FinishSpeaking();
        await WaitUntil(() => controller.State == VoiceState.Awake && callCount == 2);

        Assert.Equal(2, callCount);
        Assert.Equal(new[] { "ok", "ok" }, tts.Spoken);
    }

    [Fact]
    public async Task A_sleep_phrase_never_reaches_the_reasoning_call_and_quiets_the_microphone()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        var reasoningCalls = 0;
        using var orchestrator = new ConversationOrchestrator(
            controller, (_, _) => { reasoningCalls++; return Task.FromResult("should never run"); },
            tts, delay: NeverFires());

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("please close your ears");

        await WaitUntil(() => tts.Spoken.Count == 1);
        tts.FinishSpeaking();
        await WaitUntil(() => controller.State == VoiceState.Idle);

        Assert.Equal(0, reasoningCalls); // never sent to the model as if it were a question
        Assert.Equal("Okay, I'll stop listening.", tts.Spoken[0]);
        Assert.Equal(VoiceState.Idle, controller.State);
    }

    [Fact]
    public async Task A_shutdown_phrase_acknowledges_quiets_the_microphone_and_raises_shutdown_requested()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (_, _) => Task.FromResult("should never run"), tts, delay: NeverFires());

        var shutdownRaised = false;
        orchestrator.ShutdownRequested += () => shutdownRaised = true;

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("shut down");

        await WaitUntil(() => tts.Spoken.Count == 1);
        tts.FinishSpeaking();
        await WaitUntil(() => shutdownRaised);

        Assert.Equal("Shutting down.", tts.Spoken[0]);
        Assert.Equal(VoiceState.Idle, controller.State);
    }

    [Fact]
    public async Task Ordinary_speech_still_goes_through_the_normal_reasoning_path()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        var reasoningCalls = 0;
        using var orchestrator = new ConversationOrchestrator(
            controller, (text, _) => { reasoningCalls++; return Task.FromResult($"echo: {text}"); },
            tts, delay: NeverFires());

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("what's on my calendar today");

        await WaitUntil(() => tts.Spoken.Count == 1);
        tts.FinishSpeaking();
        await WaitUntil(() => controller.State == VoiceState.Awake);

        Assert.Equal(1, reasoningCalls);
        Assert.Equal("echo: what's on my calendar today", tts.Spoken[0]);
    }

    [Fact]
    public async Task Streaming_response_speaks_each_sentence_as_it_becomes_available()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (_, _) => Task.FromResult("unused"), tts, delay: NeverFires(),
            generateResponseStreaming: async (_, onSentence, _) =>
            {
                await onSentence("First sentence.");
                await onSentence("Second sentence.");
                return "First sentence. Second sentence.";
            });

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("tell me something");

        await WaitUntil(() => tts.Spoken.Count == 1);
        Assert.Equal(VoiceState.Speaking, controller.State); // first sentence -> Processing -> Speaking
        tts.FinishSpeaking();

        await WaitUntil(() => tts.Spoken.Count == 2);
        tts.FinishSpeaking();

        await WaitUntil(() => controller.State == VoiceState.Awake);
        Assert.Equal(new[] { "First sentence.", "Second sentence." }, tts.Spoken);
    }

    [Fact]
    public async Task A_barge_in_between_streamed_sentences_stops_further_sentences_from_being_spoken()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (_, _) => Task.FromResult("unused"), tts, delay: NeverFires(),
            generateResponseStreaming: async (_, onSentence, _) =>
            {
                await onSentence("First sentence.");
                await onSentence("Second sentence."); // must never reach SpeakAsync after the barge-in below
                return "First sentence. Second sentence.";
            });
        var doneTcs = new TaskCompletionSource<string>();
        orchestrator.ResponseSpoken += r => doneTcs.TrySetResult(r);

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("tell me something");

        await WaitUntil(() => tts.Spoken.Count == 1);
        tts.Stop();
        controller.OnBargeIn();

        await doneTcs.Task.WaitAsync(TimeSpan.FromSeconds(2));
        Assert.Single(tts.Spoken);
        Assert.Equal(1, tts.StopCount);
    }

    [Fact]
    public async Task A_streaming_response_with_no_sentence_boundary_falls_back_to_speaking_the_whole_reply()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (_, _) => Task.FromResult("unused"), tts, delay: NeverFires(),
            generateResponseStreaming: (_, _, _) => Task.FromResult("a reply with no sentence-ending punctuation"));

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("tell me something");

        await WaitUntil(() => tts.Spoken.Count == 1);
        tts.FinishSpeaking();
        await WaitUntil(() => controller.State == VoiceState.Awake);

        Assert.Equal(new[] { "a reply with no sentence-ending punctuation" }, tts.Spoken);
    }

    [Fact]
    public async Task An_empty_streaming_response_speaks_nothing_but_still_returns_to_awake()
    {
        var controller = new VoiceSessionController();
        var tts = new FakeTextToSpeech();
        using var orchestrator = new ConversationOrchestrator(
            controller, (_, _) => Task.FromResult("unused"), tts, delay: NeverFires(),
            generateResponseStreaming: (_, _, _) => Task.FromResult(string.Empty));

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("tell me something");

        await WaitUntil(() => controller.State == VoiceState.Awake);
        Assert.Empty(tts.Spoken);
    }

    private static async Task WaitUntil(Func<bool> condition, int timeoutMs = 2000)
    {
        var deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
        while (!condition())
        {
            if (DateTime.UtcNow > deadline)
            {
                throw new TimeoutException("Condition was not met in time.");
            }
            await Task.Delay(5);
        }
    }
}
