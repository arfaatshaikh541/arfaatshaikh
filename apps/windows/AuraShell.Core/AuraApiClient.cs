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
