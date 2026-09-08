using System.Net;
using AuraShell.Core;
using Xunit;

namespace AuraShell.Core.Tests;

/// <summary>
/// End-to-end (within this process's reach) proof of section 3's exact
/// sequence: boot -> real startup auth check -> Voice Mode -> hotkey ->
/// real backend PIN auth -> Backend Mode -> same hotkey -> elevation
/// genuinely revoked server-side -> Voice Mode again. Every network call
/// here goes through the real AuraApiClient against a FakeHttpMessageHandler
/// standing in for aura_core -- InterfaceShellViewModel itself is exercised
/// completely unmodified, the same principle every other test file in this
/// project uses.
/// </summary>
public class InterfaceShellViewModelTests
{
    private static (InterfaceShellViewModel Shell, FakeHttpMessageHandler Handler) MakeShell(
        TimeSpan? elevationPollInterval = null)
    {
        var handler = new FakeHttpMessageHandler();
        var httpClient = new HttpClient(handler) { BaseAddress = new Uri("http://fake-aura-core.local") };
        var shell = new InterfaceShellViewModel(new AuraApiClient(httpClient), elevationPollInterval);
        return (shell, handler);
    }

    private static void MapEnrolledWhoAmI(FakeHttpMessageHandler handler, string ownerName = "Ada") =>
        handler.MapJson(HttpMethod.Get, "/identity/whoami",
            $$"""{"enrolled": true, "owner_name": "{{ownerName}}", "device_label": "primary"}""");

    [Fact]
    public async Task StartAsync_with_a_valid_device_reaches_VoiceMode_and_starts_observing_voice_state()
    {
        var (shell, handler) = MakeShell();
        MapEnrolledWhoAmI(handler);
        handler.MapJson(HttpMethod.Get, "/voice/state", """{"state": "Idle", "reported_at": null}""");
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");

        await shell.StartAsync();

        Assert.Equal(InterfaceMode.VoiceMode, shell.Mode.Mode);
        Assert.Equal("Ada", shell.OwnerName);
        Assert.Null(shell.AuthErrorMessage);
    }

    [Fact]
    public async Task StartAsync_before_enrollment_stays_on_the_auth_screen_with_an_honest_message()
    {
        var (shell, handler) = MakeShell();
        handler.MapJson(HttpMethod.Get, "/identity/whoami",
            """{"enrolled": false, "owner_name": null, "device_label": null}""");

        await shell.StartAsync();

        Assert.Equal(InterfaceMode.AuthRequired, shell.Mode.Mode);
        Assert.Contains("enroll", shell.AuthErrorMessage);
    }

    [Fact]
    public async Task StartAsync_with_an_invalid_device_token_stays_on_the_auth_screen()
    {
        var (shell, handler) = MakeShell();
        handler.MapJson(HttpMethod.Get, "/identity/whoami", """{"detail": "unauthorized"}""", HttpStatusCode.Unauthorized);

        await shell.StartAsync();

        Assert.Equal(InterfaceMode.AuthRequired, shell.Mode.Mode);
        Assert.NotNull(shell.AuthErrorMessage);
    }

    private static async Task<InterfaceShellViewModel> StartedInVoiceModeAsync(FakeHttpMessageHandler handler)
    {
        var httpClient = new HttpClient(handler) { BaseAddress = new Uri("http://fake-aura-core.local") };
        var shell = new InterfaceShellViewModel(new AuraApiClient(httpClient));
        MapEnrolledWhoAmI(handler);
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");
        await shell.StartAsync();
        return shell;
    }

    [Fact]
    public async Task Pressing_the_hotkey_from_VoiceMode_requests_backend_authentication_without_granting_anything_yet()
    {
        var handler = new FakeHttpMessageHandler();
        var shell = await StartedInVoiceModeAsync(handler);

        await shell.RequestBackendToggleAsync();

        Assert.Equal(InterfaceMode.BackendAuthRequired, shell.Mode.Mode);
        // No /backend/authenticate call was made yet -- toggling only ever
        // requests the challenge, it never submits credentials itself.
        Assert.DoesNotContain(handler.Requests, r => r.RequestUri!.AbsolutePath == "/backend/authenticate");
    }

    [Fact]
    public async Task The_full_voice_to_backend_and_back_sequence_works_end_to_end()
    {
        var handler = new FakeHttpMessageHandler();
        var shell = await StartedInVoiceModeAsync(handler);

        // Owner presses the hotkey -- challenge only, matching section 3.
        await shell.RequestBackendToggleAsync();
        Assert.Equal(InterfaceMode.BackendAuthRequired, shell.Mode.Mode);

        // Owner enters the correct PIN.
        handler.MapJson(HttpMethod.Post, "/backend/authenticate",
            """{"elevation_token": "tok-abc", "expires_in_seconds": 900.0}""");
        handler.MapJson(HttpMethod.Get, "/status", "{}");
        handler.MapJson(HttpMethod.Get, "/approvals", "[]");
        shell.BackendPinInput = "482913";
        await shell.SubmitBackendPinAsync();

        Assert.Equal(InterfaceMode.BackendMode, shell.Mode.Mode);
        Assert.Empty(shell.BackendPinInput); // never left sitting in the field

        // Owner presses the SAME hotkey to leave -- no re-auth required to
        // leave, but elevation must be genuinely revoked server-side.
        handler.MapJson(HttpMethod.Post, "/backend/deauthenticate", """{"revoked": true}""");
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");
        await shell.RequestBackendToggleAsync();

        Assert.Equal(InterfaceMode.VoiceMode, shell.Mode.Mode);
        var deauth = Assert.Single(handler.Requests, r => r.RequestUri!.AbsolutePath == "/backend/deauthenticate");
        Assert.Equal("tok-abc", deauth.Headers.GetValues(BackendElevationHeader.Name).Single());
    }

    [Fact]
    public async Task Entering_BackendMode_loads_real_diagnostics_and_audit_and_leaving_clears_them()
    {
        var handler = new FakeHttpMessageHandler();
        var shell = await StartedInVoiceModeAsync(handler);
        await shell.RequestBackendToggleAsync();

        handler.MapJson(HttpMethod.Post, "/backend/authenticate",
            """{"elevation_token": "tok-abc", "expires_in_seconds": 900.0}""");
        handler.MapJson(HttpMethod.Get, "/status", "{}");
        handler.MapJson(HttpMethod.Get, "/approvals", "[]");
        handler.MapJson(HttpMethod.Get, "/backend/diagnostics", """
            {"audit_chain_valid": true, "audit_entries_checked": 7,
             "recent_guardian_events": [], "capability_status": {}}
            """);
        handler.MapJson(HttpMethod.Get, "/backend/audit", """
            [{"seq": 1, "timestamp": "2026-01-01T00:00:00+00:00", "actor": "owner",
              "action_type": "security.backend_elevation_attempt", "risk_tier": "RED",
              "decision": "ALLOW", "result_status": "EXECUTED", "result_message": "ok"}]
            """);
        shell.BackendPinInput = "482913";
        await shell.SubmitBackendPinAsync();

        Assert.NotNull(shell.Diagnostics);
        Assert.True(shell.Diagnostics!.AuditChainValid);
        Assert.Single(shell.AuditEntries);

        handler.MapJson(HttpMethod.Post, "/backend/deauthenticate", """{"revoked": true}""");
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");
        await shell.RequestBackendToggleAsync();

        Assert.Null(shell.Diagnostics);
        Assert.Empty(shell.AuditEntries);
    }

    [Fact]
    public async Task A_wrong_pin_returns_to_the_challenge_screen_without_saying_which_factor_was_wrong()
    {
        var handler = new FakeHttpMessageHandler();
        var shell = await StartedInVoiceModeAsync(handler);
        await shell.RequestBackendToggleAsync();

        handler.MapJson(HttpMethod.Post, "/backend/authenticate", """{"detail": "backend authentication failed"}""", HttpStatusCode.Unauthorized);
        shell.BackendPinInput = "000000";
        await shell.SubmitBackendPinAsync();

        Assert.Equal(InterfaceMode.BackendAuthRequired, shell.Mode.Mode);
        Assert.Equal("Backend authentication failed.", shell.AuthErrorMessage);
    }

    [Fact]
    public async Task Cancelling_the_backend_challenge_returns_to_VoiceMode_and_resumes_observing()
    {
        var handler = new FakeHttpMessageHandler();
        var shell = await StartedInVoiceModeAsync(handler);
        await shell.RequestBackendToggleAsync();
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");

        shell.CancelBackendAuthCommand.Execute(null);
        await Task.Delay(50); // RelayCommand.Execute is async void; give it a tick to complete

        Assert.Equal(InterfaceMode.VoiceMode, shell.Mode.Mode);
    }

    [Fact]
    public async Task An_OS_lock_from_BackendMode_revokes_elevation_before_locking()
    {
        var handler = new FakeHttpMessageHandler();
        var shell = await StartedInVoiceModeAsync(handler);
        await shell.RequestBackendToggleAsync();
        handler.MapJson(HttpMethod.Post, "/backend/authenticate",
            """{"elevation_token": "tok-abc", "expires_in_seconds": 900.0}""");
        handler.MapJson(HttpMethod.Get, "/status", "{}");
        handler.MapJson(HttpMethod.Get, "/approvals", "[]");
        shell.BackendPinInput = "482913";
        await shell.SubmitBackendPinAsync();

        handler.MapJson(HttpMethod.Post, "/backend/deauthenticate", """{"revoked": true}""");
        await shell.OnSystemLockedAsync();

        Assert.Equal(InterfaceMode.Locked, shell.Mode.Mode);
        Assert.Contains(handler.Requests, r => r.RequestUri!.AbsolutePath == "/backend/deauthenticate");
    }

    [Fact]
    public async Task Unlocking_never_restores_BackendMode_it_always_re_authenticates_from_scratch()
    {
        var handler = new FakeHttpMessageHandler();
        var shell = await StartedInVoiceModeAsync(handler);
        await shell.OnSystemLockedAsync();
        Assert.Equal(InterfaceMode.Locked, shell.Mode.Mode);

        MapEnrolledWhoAmI(handler);
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");
        await shell.OnSystemUnlockedAsync();

        Assert.Equal(InterfaceMode.VoiceMode, shell.Mode.Mode);
    }

    [Fact]
    public async Task RecoverCommand_leaves_ErrorRecovery_and_re_authenticates_from_scratch()
    {
        var handler = new FakeHttpMessageHandler();
        var shell = await StartedInVoiceModeAsync(handler);
        shell.Mode.EnterErrorRecovery();
        Assert.Equal(InterfaceMode.ErrorRecovery, shell.Mode.Mode);

        MapEnrolledWhoAmI(handler);
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");
        shell.RecoverCommand.Execute(null);
        await Task.Delay(50); // RelayCommand.Execute is async void; give it a tick to complete

        Assert.Equal(InterfaceMode.VoiceMode, shell.Mode.Mode);
    }

    [Fact]
    public async Task Elevation_expiring_server_side_is_noticed_and_returns_to_the_challenge_screen()
    {
        // Section 14: even with the UI otherwise idle, an elevation the
        // server has already expired must not go on being treated as
        // BackendMode. A fast poll interval here stands in for real
        // wall-clock time -- the server's own TTL enforcement (proven in
        // core/tests/test_backend_elevation.py) is the actual security
        // boundary; this only checks the shell notices and reacts.
        var handler = new FakeHttpMessageHandler();
        var httpClient = new HttpClient(handler) { BaseAddress = new Uri("http://fake-aura-core.local") };
        var shell = new InterfaceShellViewModel(new AuraApiClient(httpClient), elevationPollInterval: TimeSpan.FromMilliseconds(20));
        MapEnrolledWhoAmI(handler);
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");
        await shell.StartAsync();
        await shell.RequestBackendToggleAsync();

        handler.MapJson(HttpMethod.Post, "/backend/authenticate",
            """{"elevation_token": "tok-abc", "expires_in_seconds": 900.0}""");
        handler.MapJson(HttpMethod.Get, "/status", "{}");
        handler.MapJson(HttpMethod.Get, "/approvals", "[]");
        shell.BackendPinInput = "482913";
        await shell.SubmitBackendPinAsync();
        Assert.Equal(InterfaceMode.BackendMode, shell.Mode.Mode);

        // The server now reports the session as no longer active (expired
        // or revoked out-of-band) -- the shell's next poll must notice.
        handler.MapJson(HttpMethod.Get, "/backend/session", """{"active": false, "seconds_remaining": 0.0}""");
        handler.MapSseBody(HttpMethod.Get, "/voice/state/stream", "data: {\"event\": \"state\", \"data\": \"Idle\"}\n\n");

        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(2);
        while (shell.Mode.Mode != InterfaceMode.BackendAuthRequired && DateTime.UtcNow < deadline)
        {
            await Task.Delay(10);
        }

        Assert.Equal(InterfaceMode.BackendAuthRequired, shell.Mode.Mode);
        Assert.Null(shell.ElevationRemaining);
    }
}
