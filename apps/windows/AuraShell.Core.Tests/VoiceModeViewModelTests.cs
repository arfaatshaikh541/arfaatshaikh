using AuraShell.Core;
using Xunit;

namespace AuraShell.Core.Tests;

public class VoiceModeViewModelTests
{
    private static AuraApiClient MakeClient(FakeHttpMessageHandler handler)
    {
        var httpClient = new HttpClient(handler) { BaseAddress = new Uri("http://fake-aura-core.local") };
        return new AuraApiClient(httpClient);
    }

    private static async Task WaitUntil(Func<bool> condition, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (!condition())
        {
            if (DateTime.UtcNow > deadline)
            {
                throw new TimeoutException("condition was never met");
            }
            await Task.Delay(10);
        }
    }

    [Fact]
    public async Task StartObserving_reflects_every_real_pushed_state_in_order()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream",
            "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n" +
            "data: {\"event\": \"state\", \"data\": \"Awake\"}\n\n" +
            "data: {\"event\": \"state\", \"data\": \"Speaking\"}\n\n");
        var vm = new VoiceModeViewModel(MakeClient(handler));

        var seen = new List<VoiceVisualState>();
        vm.PropertyChanged += (_, e) =>
        {
            if (e.PropertyName == nameof(VoiceModeViewModel.State))
            {
                seen.Add(vm.State);
            }
        };

        vm.StartObserving();
        await WaitUntil(() => seen.Count >= 3, TimeSpan.FromSeconds(2));
        vm.StopObserving();

        Assert.Equal(new[] { VoiceVisualState.Idle, VoiceVisualState.Awake, VoiceVisualState.Speaking }, seen.Take(3));
    }

    [Fact]
    public async Task An_unreachable_server_is_reported_as_offline_not_left_stale()
    {
        var handler = new FakeHttpMessageHandler(); // no route mapped -> 404 -> EnsureSuccessStatusCode throws
        var vm = new VoiceModeViewModel(MakeClient(handler), reconnectDelay: TimeSpan.FromMilliseconds(20));

        vm.StartObserving();
        await WaitUntil(() => vm.State == VoiceVisualState.Offline, TimeSpan.FromSeconds(2));
        vm.StopObserving();

        Assert.Equal(VoiceVisualState.Offline, vm.State);
    }

    [Fact]
    public async Task Muting_holds_the_visual_state_even_while_real_transitions_keep_arriving()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream",
            "data: {\"event\": \"state\", \"data\": \"Awake\"}\n\n" +
            "data: {\"event\": \"state\", \"data\": \"Speaking\"}\n\n");
        var vm = new VoiceModeViewModel(MakeClient(handler));

        vm.SetMuted(true);
        vm.StartObserving();
        await Task.Delay(100); // give the (muted) stream a chance to be consumed
        vm.StopObserving();

        Assert.Equal(VoiceVisualState.Muted, vm.State);
        Assert.True(vm.IsMuted);
    }

    [Fact]
    public void Unmuting_returns_to_unknown_until_the_next_real_event_arrives()
    {
        var vm = new VoiceModeViewModel(MakeClient(new FakeHttpMessageHandler()));

        vm.SetMuted(true);
        vm.SetMuted(false);

        Assert.False(vm.IsMuted);
        Assert.Equal(VoiceVisualState.Unknown, vm.State);
    }

    [Fact]
    public async Task SetMuted_pushes_the_real_FullMicOff_mode_to_aura_core()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/voice/privacy", """{"mode": "FullMicOff"}""");
        var vm = new VoiceModeViewModel(MakeClient(handler));

        vm.SetMuted(true);
        await WaitUntil(() => handler.Requests.Count >= 1, TimeSpan.FromSeconds(1));

        var request = Assert.Single(handler.Requests);
        Assert.Equal("/voice/privacy", request.RequestUri!.AbsolutePath);
        var body = await request.Content!.ReadAsStringAsync();
        Assert.Contains("\"mode\":\"FullMicOff\"", body);
    }

    [Fact]
    public async Task SetWakeWordOnly_pushes_the_real_WakeWordOnly_mode_and_is_mutually_exclusive_with_mute()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/voice/privacy", """{"mode": "WakeWordOnly"}""");
        var vm = new VoiceModeViewModel(MakeClient(handler));

        vm.SetMuted(true);
        vm.SetWakeWordOnly(true);
        await WaitUntil(() => handler.Requests.Count >= 2, TimeSpan.FromSeconds(1));

        Assert.True(vm.IsWakeWordOnly);
        Assert.False(vm.IsMuted); // enabling wake-word-only clears mute
        var lastBody = await handler.Requests[^1].Content!.ReadAsStringAsync();
        Assert.Contains("\"mode\":\"WakeWordOnly\"", lastBody);
    }

    [Fact]
    public void Enabling_mute_while_wake_word_only_is_active_clears_wake_word_only()
    {
        var vm = new VoiceModeViewModel(MakeClient(new FakeHttpMessageHandler()));

        vm.SetWakeWordOnly(true);
        vm.SetMuted(true);

        Assert.True(vm.IsMuted);
        Assert.False(vm.IsWakeWordOnly);
    }

    [Theory]
    [InlineData("Idle", VoiceVisualState.Idle)]
    [InlineData("ListeningForWake", VoiceVisualState.ListeningForWake)]
    [InlineData("Awake", VoiceVisualState.Awake)]
    [InlineData("Processing", VoiceVisualState.Processing)]
    [InlineData("Speaking", VoiceVisualState.Speaking)]
    [InlineData("TotallyMadeUp", VoiceVisualState.Unknown)]
    public void ParseState_maps_every_real_VoiceSessionController_state(string raw, VoiceVisualState expected)
    {
        Assert.Equal(expected, VoiceModeViewModel.ParseState(raw));
    }
}
