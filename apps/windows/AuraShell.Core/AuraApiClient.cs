using System.Net.Http.Json;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;

namespace AuraShell.Core;

/// <summary>
/// Talks to the real AURA core FastAPI server (core/src/aura_core/api/app.py)
/// over HTTP. Every method here does a genuine network call — there is no
/// mock mode baked into this class. Tests exercise it against a fake
/// HttpMessageHandler that returns canned HTTP responses (including a real
/// SSE-formatted byte stream for the streaming test), which proves the
/// parsing logic is correct without requiring a live server — the same
/// principle the Python side's DeterministicTestProvider uses.
/// </summary>
public sealed class AuraApiClient
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    private readonly HttpClient _http;

    public AuraApiClient(HttpClient httpClient)
    {
        _http = httpClient;
    }

    public async Task<bool> IsHealthyAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _http.GetAsync("/health", ct);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException)
        {
            return false;
        }
    }

    public async Task<Dictionary<string, CapabilityInfo>> GetStatusAsync(CancellationToken ct = default)
    {
        var result = await _http.GetFromJsonAsync<Dictionary<string, CapabilityInfo>>(
            "/status", JsonOptions, ct);
        return result ?? new Dictionary<string, CapabilityInfo>();
    }

    public async Task<List<ApprovalInfo>> GetApprovalsAsync(CancellationToken ct = default)
    {
        var result = await _http.GetFromJsonAsync<List<ApprovalInfo>>("/approvals", JsonOptions, ct);
        return result ?? new List<ApprovalInfo>();
    }

    public async Task<ApprovalDecisionResult> DecideApprovalAsync(
        string approvalId, bool approved, string decidedBy, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/approvals/{approvalId}/decide",
            new { approved, decided_by = decidedBy },
            ct);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<ApprovalDecisionResult>(JsonOptions, ct);
        return result ?? new ApprovalDecisionResult("UNKNOWN", "no response body");
    }

    public async Task<List<AuditEntryInfo>> GetAuditAsync(CancellationToken ct = default)
    {
        var result = await _http.GetFromJsonAsync<List<AuditEntryInfo>>("/audit", JsonOptions, ct);
        return result ?? new List<AuditEntryInfo>();
    }

    public async Task<AuditVerification> GetAuditVerifyAsync(CancellationToken ct = default)
    {
        var result = await _http.GetFromJsonAsync<AuditVerification>("/audit/verify", JsonOptions, ct);
        return result ?? new AuditVerification(false, null, 0);
    }

    public Task EngageKillSwitchAsync(CancellationToken ct = default) =>
        _http.PostAsync("/kill-switch/engage", content: null, ct);

    public Task DisengageKillSwitchAsync(CancellationToken ct = default) =>
        _http.PostAsync("/kill-switch/disengage", content: null, ct);

    /// <summary>
    /// Pushes the voice pipeline's current VoiceSessionController state
    /// to aura_core so any local client (a future tray icon, this same
    /// shell's Status tab, `aura status`) can see real listening/
    /// speaking status without talking to the voice host process
    /// directly -- section 8's "privacy-visible status," the backend
    /// half that doesn't need a Windows machine to build or test.
    /// </summary>
    public async Task ReportVoiceStateAsync(string state, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync("/voice/state", new { state }, ct);
        response.EnsureSuccessStatusCode();
    }

    public async Task<VoiceStateInfo> GetVoiceStateAsync(CancellationToken ct = default)
    {
        var result = await _http.GetFromJsonAsync<VoiceStateInfo>("/voice/state", JsonOptions, ct);
        return result ?? new VoiceStateInfo("UNKNOWN", null);
    }

    /// <summary>
    /// The real backend half of "FULL MIC OFF vs. WAKE-WORD-ONLY"
    /// (section 17): this is what AuraVoice.Windows.Host actually polls
    /// and hands to WindowsVoicePipeline.PrivacyGate, which opens/closes
    /// the real microphone hardware. VoiceModeViewModel calls this from
    /// its mute/wake-word-only toggles -- the WPF UI is a client of this
    /// state, never the thing that gates the microphone itself.
    /// </summary>
    public async Task SetVoicePrivacyAsync(string mode, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync("/voice/privacy", new { mode }, ct);
        response.EnsureSuccessStatusCode();
    }

    public async Task<VoicePrivacyInfo> GetVoicePrivacyAsync(CancellationToken ct = default)
    {
        var result = await _http.GetFromJsonAsync<VoicePrivacyInfo>("/voice/privacy", JsonOptions, ct);
        return result ?? new VoicePrivacyInfo("Normal");
    }

    /// <summary>
    /// Ungated on purpose (see api/app.py's /interface/config) -- the
    /// shell reads this before the owner has authenticated at all, to
    /// know which hotkey to register and which mode to boot into.
    /// </summary>
    public async Task<InterfaceConfig> GetInterfaceConfigAsync(CancellationToken ct = default)
    {
        var result = await _http.GetFromJsonAsync<InterfaceConfig>("/interface/config", JsonOptions, ct);
        return result ?? new InterfaceConfig("voice", "Ctrl+Alt+Shift+A", true, 900);
    }

    /// <summary>
    /// The real Backend Mode entry point: presents the owner's PIN
    /// alongside the already-attached device token. A wrong PIN or an
    /// untrusted device throws HttpRequestException (401); too many
    /// recent failures throws it with a 429 the caller can inspect via
    /// StatusCode -- InterfaceModeManager is expected to surface both as
    /// "authentication failed," never distinguishing which factor was
    /// wrong, matching the server's own refusal to say.
    /// </summary>
    public async Task<BackendAuthResult> BackendAuthenticateAsync(string pin, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync("/backend/authenticate", new { pin }, ct);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<BackendAuthResult>(JsonOptions, ct);
        return result ?? throw new InvalidOperationException("backend authentication succeeded but returned no elevation token");
    }

    /// <summary>
    /// Always safe to call, including with an already-expired or unknown
    /// token -- revocation is idempotent by design (see
    /// identity/elevation.py). InterfaceModeManager calls this
    /// unconditionally on every Backend -> Voice transition.
    /// </summary>
    public async Task BackendDeauthenticateAsync(string elevationToken, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/backend/deauthenticate");
        request.Headers.Add(BackendElevationHeader.Name, elevationToken);
        using var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
    }

    /// <summary>
    /// Returns null for an expired/unknown token rather than throwing --
    /// this is a routine liveness poll (e.g. the shell checking whether
    /// it should self-downgrade before the server would reject the next
    /// real request), not a security decision point itself.
    /// </summary>
    public async Task<BackendSessionStatus?> GetBackendSessionAsync(string elevationToken, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/backend/session");
        request.Headers.Add(BackendElevationHeader.Name, elevationToken);
        using var response = await _http.SendAsync(request, ct);
        if (!response.IsSuccessStatusCode)
        {
            return null;
        }
        return await response.Content.ReadFromJsonAsync<BackendSessionStatus>(JsonOptions, ct);
    }

    /// <summary>
    /// The startup authentication check (section 3): asks aura_core
    /// whether the calling device already carries a valid device token
    /// and, if so, who the owner is. A 401 here (thrown as
    /// HttpRequestException, matching every other gated call in this
    /// class) means the device token is missing, wrong, or revoked --
    /// AuthenticationViewModel treats that identically to "not yet
    /// authenticated," never distinguishing why, same as the server.
    /// </summary>
    public async Task<WhoAmIInfo> GetWhoAmIAsync(CancellationToken ct = default)
    {
        var response = await _http.GetAsync("/identity/whoami", ct);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<WhoAmIInfo>(JsonOptions, ct);
        return result ?? new WhoAmIInfo(false, null, null);
    }

    public async Task<BackendDiagnostics> GetBackendDiagnosticsAsync(string elevationToken, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/backend/diagnostics");
        request.Headers.Add(BackendElevationHeader.Name, elevationToken);
        using var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<BackendDiagnostics>(JsonOptions, ct);
        return result ?? throw new InvalidOperationException("backend diagnostics returned no response body");
    }

    public async Task<List<AuditEntryInfo>> GetBackendAuditAsync(
        string elevationToken, long afterSeq = 0, int limit = 100, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, $"/backend/audit?after_seq={afterSeq}&limit={limit}");
        request.Headers.Add(BackendElevationHeader.Name, elevationToken);
        using var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<List<AuditEntryInfo>>(JsonOptions, ct);
        return result ?? new List<AuditEntryInfo>();
    }

    /// <summary>
    /// Real multi-device trust (identity/enrollment.py's DeviceTrust) --
    /// never returns a token, only the metadata every device row already
    /// carried before this HTTP surface existed (label, timestamps,
    /// revocation state).
    /// </summary>
    public async Task<List<DeviceInfo>> GetDevicesAsync(string elevationToken, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/devices");
        request.Headers.Add(BackendElevationHeader.Name, elevationToken);
        using var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<List<DeviceInfo>>(JsonOptions, ct);
        return result ?? new List<DeviceInfo>();
    }

    /// <summary>Idempotent -- safe to call again for an already-revoked
    /// or unknown device id (matches EnrollmentEngine.revoke_device's own
    /// silent no-op on an unknown id).</summary>
    public async Task RevokeDeviceAsync(string deviceId, string elevationToken, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, $"/devices/{deviceId}/revoke");
        request.Headers.Add(BackendElevationHeader.Name, elevationToken);
        using var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
    }

    public async Task RenameDeviceAsync(string deviceId, string newLabel, string elevationToken, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, $"/devices/{deviceId}/rename")
        {
            Content = JsonContent.Create(new { label = newLabel }),
        };
        request.Headers.Add(BackendElevationHeader.Name, elevationToken);
        using var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
    }

    /// <summary>
    /// The "Add Device" flow's root-side half (section 15/16): requires
    /// backend elevation, same as every other privileged device
    /// operation -- only an already-authenticated, already-elevated
    /// owner may authorize a brand-new device to join.
    /// </summary>
    public async Task<PairingSessionInfo> StartDevicePairingAsync(string elevationToken, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/devices/pairing/start");
        request.Headers.Add(BackendElevationHeader.Name, elevationToken);
        using var response = await _http.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<PairingSessionInfo>(JsonOptions, ct);
        return result ?? throw new InvalidOperationException("pairing start succeeded but returned no session body");
    }

    /// <summary>
    /// The "Add Device" flow's new-device-side half: deliberately no
    /// elevation or device-token header is attached here -- this device
    /// has neither yet. Its only credential is the pairing code itself.
    /// Throws HttpRequestException (401) for an invalid, already-used,
    /// or expired code, never distinguishing which.
    /// </summary>
    public async Task<string> ClaimDevicePairingAsync(string code, string deviceLabel, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            "/devices/pairing/claim", new { code, device_label = deviceLabel }, ct);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<PairingClaimResult>(JsonOptions, ct);
        return result?.DeviceToken ?? throw new InvalidOperationException("pairing claim succeeded but returned no device token");
    }

    /// <summary>
    /// Consumes /voice/state/stream's genuine server push -- one HTTP
    /// request stays open for the lifetime of enumeration, and a new
    /// state string is yielded exactly when aura_core observed a real
    /// transition, never on a fixed timer the caller has to de-duplicate.
    /// This is what lets VoiceModeViewModel bind to live voice state
    /// without ever polling GetVoiceStateAsync in a loop (section 6).
    /// The enumeration only ends when the caller cancels ct or the
    /// connection drops -- callers are expected to run this inside a
    /// background task, the same pattern AuraVoice.Windows.Host already
    /// uses for its own long-running loop.
    /// </summary>
    public async IAsyncEnumerable<string> StreamVoiceStateAsync(
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        using var response = await _http.SendAsync(
            new HttpRequestMessage(HttpMethod.Get, "/voice/state/stream"),
            HttpCompletionOption.ResponseHeadersRead, ct);
        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var reader = new StreamReader(stream, Encoding.UTF8);

        while (!reader.EndOfStream)
        {
            var line = await reader.ReadLineAsync(ct);
            if (line is null)
            {
                yield break;
            }
            if (!line.StartsWith("data: ", StringComparison.Ordinal))
            {
                continue;
            }
            var evt = JsonSerializer.Deserialize<ChatEvent>(line["data: ".Length..], JsonOptions);
            if (evt is not null)
            {
                yield return evt.Data;
            }
        }
    }

    /// <summary>
    /// Streams /chat as it genuinely arrives. Reads the response body line
    /// by line and yields a ChatEvent per "data: {...}" line — no
    /// buffering of the full response before the first event is produced,
    /// which is what makes this a real streaming client rather than a
    /// fake one that reveals a complete response incrementally.
    /// </summary>
    public async IAsyncEnumerable<ChatEvent> ChatStreamAsync(
        string message, [EnumeratorCancellation] CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/chat")
        {
            Content = JsonContent.Create(new { message }),
        };

        using var response = await _http.SendAsync(
            request, HttpCompletionOption.ResponseHeadersRead, ct);
        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var reader = new StreamReader(stream, Encoding.UTF8);

        while (!reader.EndOfStream)
        {
            var line = await reader.ReadLineAsync(ct);
            if (line is null)
            {
                yield break;
            }

            if (!line.StartsWith("data: ", StringComparison.Ordinal))
            {
                continue; // blank keep-alive lines between SSE events
            }

            var json = line["data: ".Length..];
            var chatEvent = JsonSerializer.Deserialize<ChatEvent>(json, JsonOptions);
            if (chatEvent is not null)
            {
                yield return chatEvent;
            }
        }
    }
}
