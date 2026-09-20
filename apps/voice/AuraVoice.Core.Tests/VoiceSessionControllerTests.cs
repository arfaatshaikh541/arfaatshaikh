using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

public class VoiceSessionControllerTests
{
    [Fact]
    public void Happy_path_wake_to_speak_to_conversation_window_to_timeout()
    {
        var controller = new VoiceSessionController();
        var states = new List<VoiceState>();
        controller.StateChanged += states.Add;

        var wakeFired = false;
        controller.WakeWordDetected += () => wakeFired = true;

        string? capturedCommand = null;
        controller.CommandCaptured += text => capturedCommand = text;

        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        Assert.True(wakeFired);
        Assert.Equal(VoiceState.Awake, controller.State);

        controller.OnCommandCaptured("what happened today?");
        Assert.Equal("what happened today?", capturedCommand);
        Assert.Equal(VoiceState.Processing, controller.State);

        controller.OnResponseReady();
        Assert.Equal(VoiceState.Speaking, controller.State);

        controller.OnSpeakingFinished();
        Assert.Equal(VoiceState.Awake, controller.State); // conversation window, no re-wake needed

        controller.OnConversationTimeout();
        Assert.Equal(VoiceState.ListeningForWake, controller.State);

        Assert.Equal(
            new[]
            {
                VoiceState.ListeningForWake, VoiceState.Awake, VoiceState.Processing,
                VoiceState.Speaking, VoiceState.Awake, VoiceState.ListeningForWake,
            },
            states);
    }

    [Fact]
    public void Barge_in_during_speaking_returns_to_awake_and_raises_event()
    {
        var controller = new VoiceSessionController();
        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("tell me a long story");
        controller.OnResponseReady();

        var bargeInFired = false;
        controller.BargeInRequested += () => bargeInFired = true;

        controller.OnBargeIn();

        Assert.True(bargeInFired);
        Assert.Equal(VoiceState.Awake, controller.State);
    }

    [Fact]
    public void Sleep_works_from_any_state_including_mid_conversation()
    {
        var controller = new VoiceSessionController();
        controller.StartWakeListening();
        controller.OnWakeWordDetected();
        controller.OnCommandCaptured("do something");

        controller.Sleep(); // "close your ears" mid-processing

        Assert.Equal(VoiceState.Idle, controller.State);
    }

    [Fact]
    public void StartWakeListening_is_idempotent_when_already_listening()
    {
        var controller = new VoiceSessionController();
        controller.StartWakeListening();
        controller.StartWakeListening(); // must not throw

        Assert.Equal(VoiceState.ListeningForWake, controller.State);
    }

    [Fact]
    public void Illegal_transition_throws_with_a_clear_message()
    {
        var controller = new VoiceSessionController(); // starts Idle

        var ex = Assert.Throws<InvalidOperationException>(() => controller.OnWakeWordDetected());
        Assert.Contains("ListeningForWake", ex.Message);
        Assert.Contains("Idle", ex.Message);
    }

    [Fact]
    public void Wake_up_after_sleep_requires_going_through_idle()
    {
        var controller = new VoiceSessionController();
        controller.StartWakeListening();
        controller.OnWakeWordDetected();

        controller.Sleep();
        Assert.Equal(VoiceState.Idle, controller.State);

        controller.StartWakeListening(); // "wake up"
        Assert.Equal(VoiceState.ListeningForWake, controller.State);
    }
}
