using System.Linq;
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

    [Fact]
    public async Task GetInterfaceConfigAsync_deserializes_the_real_config_shape()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/interface/config", """
            {"default_interface_mode": "voice", "backend_toggle_hotkey": "Ctrl+Alt+Shift+A",
             "require_backend_reauth": true, "backend_elevation_ttl_seconds": 900}
            """);
        var client = MakeClient(handler);

        var config = await client.GetInterfaceConfigAsync();

        Assert.Equal("voice", config.DefaultInterfaceMode);
        Assert.Equal("Ctrl+Alt+Shift+A", config.BackendToggleHotkey);
        Assert.True(config.RequireBackendReauth);
    }

    [Fact]
    public async Task BackendAuthenticateAsync_posts_the_pin_and_returns_the_elevation_token()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/backend/authenticate", """
            {"elevation_token": "tok-123", "expires_in_seconds": 900.0}
            """);
        var client = MakeClient(handler);

        var result = await client.BackendAuthenticateAsync("482913");

        Assert.Equal("tok-123", result.ElevationToken);
        Assert.Equal(900.0, result.ExpiresInSeconds);
        var request = Assert.Single(handler.Requests);
        var body = await request.Content!.ReadAsStringAsync();
        Assert.Contains("482913", body);
    }

    [Fact]
    public async Task BackendAuthenticateAsync_throws_on_a_401_without_leaking_which_factor_was_wrong()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/backend/authenticate", """{"detail": "backend authentication failed"}""", HttpStatusCode.Unauthorized);
        var client = MakeClient(handler);

        await Assert.ThrowsAsync<HttpRequestException>(() => client.BackendAuthenticateAsync("000000"));
    }

    [Fact]
    public async Task BackendDeauthenticateAsync_attaches_the_elevation_header_not_the_device_token_header()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/backend/deauthenticate", """{"revoked": true}""");
        var client = MakeClient(handler);

        await client.BackendDeauthenticateAsync("tok-123");

        var request = Assert.Single(handler.Requests);
        Assert.Equal("tok-123", request.Headers.GetValues(BackendElevationHeader.Name).Single());
        Assert.False(request.Headers.Contains(DeviceTokenHeader.Name));
    }

    [Fact]
    public async Task GetBackendSessionAsync_returns_null_for_an_expired_or_unknown_token_rather_than_throwing()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/backend/session", """{"detail": "no active backend elevation"}""", HttpStatusCode.Unauthorized);
        var client = MakeClient(handler);

        var status = await client.GetBackendSessionAsync("expired-token");

        Assert.Null(status);
    }

    [Fact]
    public async Task GetBackendSessionAsync_returns_the_real_remaining_time_for_an_active_session()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/backend/session", """{"active": true, "seconds_remaining": 842.5}""");
        var client = MakeClient(handler);

        var status = await client.GetBackendSessionAsync("tok-123");

        Assert.NotNull(status);
        Assert.True(status!.Active);
        Assert.Equal(842.5, status.SecondsRemaining);
    }

    [Fact]
    public async Task GetWhoAmIAsync_reports_that_no_owner_is_enrolled_yet()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/identity/whoami", """
            {"enrolled": false, "owner_name": null, "device_label": null}
            """);
        var client = MakeClient(handler);

        var whoami = await client.GetWhoAmIAsync();

        Assert.False(whoami.Enrolled);
        Assert.Null(whoami.OwnerName);
    }

    [Fact]
    public async Task GetWhoAmIAsync_reports_the_real_owner_and_device_once_enrolled()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/identity/whoami", """
            {"enrolled": true, "owner_name": "Ada", "device_label": "Ada's laptop"}
            """);
        var client = MakeClient(handler);

        var whoami = await client.GetWhoAmIAsync();

        Assert.True(whoami.Enrolled);
        Assert.Equal("Ada", whoami.OwnerName);
        Assert.Equal("Ada's laptop", whoami.DeviceLabel);
    }

    [Fact]
    public async Task GetWhoAmIAsync_throws_on_an_invalid_device_token()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/identity/whoami", """{"detail": "unauthorized"}""", HttpStatusCode.Unauthorized);
        var client = MakeClient(handler);

        await Assert.ThrowsAsync<HttpRequestException>(() => client.GetWhoAmIAsync());
    }

    [Fact]
    public async Task GetBackendDiagnosticsAsync_attaches_the_elevation_header_and_parses_real_fields()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/backend/diagnostics", """
            {"audit_chain_valid": true, "audit_entries_checked": 42,
             "recent_guardian_events": [], "capability_status": {"memory.store": "LIVE"}}
            """);
        var client = MakeClient(handler);

        var diagnostics = await client.GetBackendDiagnosticsAsync("tok-123");

        Assert.True(diagnostics.AuditChainValid);
        Assert.Equal(42, diagnostics.AuditEntriesChecked);
        var request = Assert.Single(handler.Requests);
        Assert.Equal("tok-123", request.Headers.GetValues(BackendElevationHeader.Name).Single());
    }

    [Fact]
    public async Task GetBackendAuditAsync_attaches_the_elevation_header_and_paginates()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/backend/audit", """
            [{"seq": 1, "timestamp": "2026-01-01T00:00:00+00:00", "actor": "owner",
              "action_type": "security.backend_elevation_attempt", "risk_tier": "RED",
              "decision": "ALLOW", "result_status": "EXECUTED", "result_message": "ok"}]
            """);
        var client = MakeClient(handler);

        var entries = await client.GetBackendAuditAsync("tok-123", afterSeq: 5, limit: 10);

        var entry = Assert.Single(entries);
        Assert.Equal(1, entry.Seq);
        var request = Assert.Single(handler.Requests);
        Assert.Equal("tok-123", request.Headers.GetValues(BackendElevationHeader.Name).Single());
        Assert.Contains("after_seq=5", request.RequestUri!.Query);
        Assert.Contains("limit=10", request.RequestUri!.Query);
    }

    [Fact]
    public async Task GetDevicesAsync_attaches_the_elevation_header_and_never_needs_a_token_field()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/devices", """
            [{"id": "d1", "label": "primary", "created_at": "2026-01-01T00:00:00+00:00",
              "last_seen_at": null, "revoked": false, "revoked_at": null}]
            """);
        var client = MakeClient(handler);

        var devices = await client.GetDevicesAsync("tok-123");

        var device = Assert.Single(devices);
        Assert.Equal("primary", device.Label);
        Assert.False(device.Revoked);
        var request = Assert.Single(handler.Requests);
        Assert.Equal("tok-123", request.Headers.GetValues(BackendElevationHeader.Name).Single());
    }

    [Fact]
    public async Task RevokeDeviceAsync_posts_to_the_correct_device_id()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/devices/d1/revoke", """{"revoked": true}""");
        var client = MakeClient(handler);

        await client.RevokeDeviceAsync("d1", "tok-123");

        var request = Assert.Single(handler.Requests);
        Assert.Equal("/devices/d1/revoke", request.RequestUri!.AbsolutePath);
        Assert.Equal("tok-123", request.Headers.GetValues(BackendElevationHeader.Name).Single());
    }

    [Fact]
    public async Task RenameDeviceAsync_posts_the_new_label()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/devices/d1/rename", """{"id": "d1", "label": "Ada Desktop"}""");
        var client = MakeClient(handler);

        await client.RenameDeviceAsync("d1", "Ada Desktop", "tok-123");

        var request = Assert.Single(handler.Requests);
        var body = await request.Content!.ReadAsStringAsync();
        Assert.Contains("Ada Desktop", body);
    }

    [Fact]
    public async Task StartDevicePairingAsync_returns_the_real_code_and_expiry()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/devices/pairing/start", """
            {"code": "ABCD1234", "expires_at": "2026-01-01T00:10:00+00:00"}
            """);
        var client = MakeClient(handler);

        var session = await client.StartDevicePairingAsync("tok-123");

        Assert.Equal("ABCD1234", session.Code);
        var request = Assert.Single(handler.Requests);
        Assert.Equal("tok-123", request.Headers.GetValues(BackendElevationHeader.Name).Single());
    }

    [Fact]
    public async Task StartDevicePairingAsync_also_deserializes_the_qr_fields_when_present()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/devices/pairing/start", """
            {"code": "ABCD1234", "expires_at": "2026-01-01T00:10:00+00:00",
             "qr_payload": "aura-pair://ABCD1234@http://192.168.1.14:8756",
             "qr_png_base64": "iVBORw0KGgo="}
            """);
        var client = MakeClient(handler);

        var session = await client.StartDevicePairingAsync("tok-123");

        Assert.Equal("aura-pair://ABCD1234@http://192.168.1.14:8756", session.QrPayload);
        Assert.Equal("iVBORw0KGgo=", session.QrPngBase64);
    }

    [Fact]
    public async Task ClaimDevicePairingAsync_never_attaches_a_device_token_or_elevation_header()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/devices/pairing/claim", """{"device_token": "new-token-abc"}""");
        var client = MakeClient(handler);

        var token = await client.ClaimDevicePairingAsync("ABCD1234", "iPhone");

        Assert.Equal("new-token-abc", token);
        var request = Assert.Single(handler.Requests);
        Assert.False(request.Headers.Contains(DeviceTokenHeader.Name));
        Assert.False(request.Headers.Contains(BackendElevationHeader.Name));
        var body = await request.Content!.ReadAsStringAsync();
        Assert.Contains("ABCD1234", body);
        Assert.Contains("iPhone", body);
    }

    [Fact]
    public async Task ClaimDevicePairingAsync_throws_on_an_invalid_or_expired_code()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/devices/pairing/claim", """{"detail": "invalid"}""", HttpStatusCode.Unauthorized);
        var client = MakeClient(handler);

        await Assert.ThrowsAsync<HttpRequestException>(() => client.ClaimDevicePairingAsync("WRONGCODE", "iPhone"));
    }

    [Fact]
    public async Task StreamVoiceStateAsync_yields_each_pushed_state_in_order()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream",
            "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n" +
            "data: {\"event\": \"state\", \"data\": \"Awake\"}\n\n" +
            "data: {\"event\": \"state\", \"data\": \"Speaking\"}\n\n");
        var client = MakeClient(handler);

        var states = new List<string>();
        await foreach (var state in client.StreamVoiceStateAsync())
        {
            states.Add(state);
        }

        Assert.Equal(new[] { "Idle", "Awake", "Speaking" }, states);
    }

    [Fact]
    public async Task SetVoicePrivacyAsync_posts_the_real_mode_string()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/voice/privacy", """{"mode": "FullMicOff"}""");
        var client = MakeClient(handler);

        await client.SetVoicePrivacyAsync("FullMicOff");

        var request = Assert.Single(handler.Requests);
        Assert.Equal(HttpMethod.Post, request.Method);
        var body = await request.Content!.ReadAsStringAsync();
        Assert.Contains("\"mode\":\"FullMicOff\"", body);
    }

    [Fact]
    public async Task GetVoicePrivacyAsync_deserializes_the_current_mode()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Get, "/voice/privacy", """{"mode": "WakeWordOnly"}""");
        var client = MakeClient(handler);

        var privacy = await client.GetVoicePrivacyAsync();

        Assert.Equal("WakeWordOnly", privacy.Mode);
    }

    private sealed class ThrowingHandler : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => throw new HttpRequestException("simulated connection failure");
    }
}
