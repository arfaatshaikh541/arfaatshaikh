using System.Net;
using AuraShell.Core;
using Xunit;

namespace AuraShell.Core.Tests;

public class AuraApiClientTests
{
    private static AuraApiClient MakeClient(FakeHttpMessageHandler handler)
    {
        var httpClient = new HttpClient(handler) { BaseAddress = new Uri("http://fake-aura-core.local") };
        return new AuraApiClient(httpClient);
    }

    [Fact]
    public async Task GetStatusAsync_deserializes_snake_case_fields()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/status", """
            {
              "memory.store": {"status": "LIVE", "detail": "connected", "checked_at": "2026-01-01T00:00:00+00:00"},
              "voice.wake_word": {"status": "NOT_CONNECTED", "detail": "no audio hardware", "checked_at": "2026-01-01T00:00:00+00:00"}
            }
            """);
        var client = MakeClient(handler);

        var status = await client.GetStatusAsync();

        Assert.Equal(2, status.Count);
        Assert.Equal("LIVE", status["memory.store"].Status);
        Assert.Equal("NOT_CONNECTED", status["voice.wake_word"].Status);
        Assert.Equal("no audio hardware", status["voice.wake_word"].Detail);
    }

    [Fact]
    public async Task IsHealthyAsync_returns_false_when_the_connection_itself_fails()
    {
        var client = new AuraApiClient(new HttpClient(new ThrowingHandler()) { BaseAddress = new Uri("http://fake.local") });

        Assert.False(await client.IsHealthyAsync());
    }

    [Fact]
    public async Task IsHealthyAsync_returns_true_when_the_server_responds_ok()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/health", """{"status": "ok"}""");
        var client = MakeClient(handler);

        Assert.True(await client.IsHealthyAsync());
    }

    [Fact]
    public async Task ChatStreamAsync_parses_a_real_multi_event_sse_response_in_order()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapSseBody("/chat",
            "data: {\"event\": \"lane\", \"data\": \"model\"}\n\n" +
            "data: {\"event\": \"chunk\", \"data\": \"Grid\"}\n\n" +
            "data: {\"event\": \"chunk\", \"data\": \"keep\"}\n\n" +
            "data: {\"event\": \"done\", \"data\": \"ok\"}\n\n");
        var client = MakeClient(handler);

        var events = new List<ChatEvent>();
        await foreach (var evt in client.ChatStreamAsync("tell me about Gridkeep"))
        {
            events.Add(evt);
        }

        Assert.Equal(4, events.Count);
        Assert.Equal(("lane", "model"), (events[0].Event, events[0].Data));
        Assert.Equal(("chunk", "Grid"), (events[1].Event, events[1].Data));
        Assert.Equal(("chunk", "keep"), (events[2].Event, events[2].Data));
        Assert.Equal(("done", "ok"), (events[3].Event, events[3].Data));

        var request = Assert.Single(handler.Requests);
        Assert.Equal(HttpMethod.Post, request.Method);
        Assert.Equal("/chat", request.RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task DecideApprovalAsync_posts_the_correct_body_and_parses_the_result()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/approvals/abc-123/decide",
            """{"status": "EXECUTED", "message": "published"}""");
        var client = MakeClient(handler);

        var result = await client.DecideApprovalAsync("abc-123", approved: true, decidedBy: "owner");

        Assert.Equal("EXECUTED", result.Status);
        Assert.Equal("published", result.Message);

        var request = Assert.Single(handler.Requests);
        var body = await request.Content!.ReadAsStringAsync();
        Assert.Contains("\"approved\":true", body);
        Assert.Contains("\"decided_by\":\"owner\"", body);
    }

    [Fact]
    public async Task GetAuditVerifyAsync_reports_a_broken_chain_honestly()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/audit/verify",
            """{"valid": false, "broken_at_seq": 3, "entries_checked": 5}""");
        var client = MakeClient(handler);

        var verification = await client.GetAuditVerifyAsync();

        Assert.False(verification.Valid);
        Assert.Equal(3, verification.BrokenAtSeq);
        Assert.Equal(5, verification.EntriesChecked);
    }

    [Fact]
    public async Task EngageKillSwitchAsync_posts_to_the_correct_endpoint()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/kill-switch/engage", """{"kill_switch_engaged": true}""");
        var client = MakeClient(handler);

        await client.EngageKillSwitchAsync();

        var request = Assert.Single(handler.Requests);
        Assert.Equal(HttpMethod.Post, request.Method);
        Assert.Equal("/kill-switch/engage", request.RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task ReportVoiceStateAsync_posts_the_real_state_string()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/voice/state", """{"state": "Awake"}""");
        var client = MakeClient(handler);

        await client.ReportVoiceStateAsync("Awake");

        var request = Assert.Single(handler.Requests);
        Assert.Equal(HttpMethod.Post, request.Method);
        Assert.Equal("/voice/state", request.RequestUri!.AbsolutePath);
        var body = await request.Content!.ReadAsStringAsync();
        Assert.Contains("\"state\":\"Awake\"", body);
    }

    [Fact]
    public async Task GetVoiceStateAsync_deserializes_the_current_state()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/voice/state", """{"state": "Speaking", "reported_at": "2026-01-01T00:00:00+00:00"}""");
        var client = MakeClient(handler);

        var state = await client.GetVoiceStateAsync();

        Assert.Equal("Speaking", state.State);
        Assert.Equal("2026-01-01T00:00:00+00:00", state.ReportedAt);
    }

    private sealed class ThrowingHandler : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => throw new HttpRequestException("simulated connection failure");
    }
}
