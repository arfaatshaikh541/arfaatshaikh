using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace AuraVoice.Core;

/// <summary>
/// Wake word / STT providers backed by the aura_core HTTP API's
/// /voice/wake-word/check and /voice/stt/transcribe endpoints (real
/// openWakeWord / sherpa-onnx models on the Python side — see
/// core/src/aura_core/voice/). Kept in AuraVoice.Core (not
/// AuraVoice.Windows) because they only exchange PCM16 bytes over HTTP —
/// no platform-specific audio API is involved here, only in the actual
/// microphone capture and speaker playback around them.
/// </summary>
public sealed class HttpWakeWordDetector : IWakeWordDetector
{
    private sealed record CheckResponse(
        [property: JsonPropertyName("score")] double Score,
        [property: JsonPropertyName("detected")] bool Detected);

    private readonly HttpClient _http;

    public HttpWakeWordDetector(HttpClient httpClient)
    {
        _http = httpClient;
    }

    /// <summary>
    /// Synchronous by interface contract (ProcessFrame is called from a
    /// tight per-frame audio callback in WindowsVoicePipeline). Blocking
    /// on an HTTP round-trip per frame is a real latency cost worth
    /// revisiting (e.g. batching frames, or making the pipeline's frame
    /// loop async) once this runs against real audio and the actual
    /// latency is measured — not optimized here without that data.
    /// </summary>
    public bool ProcessFrame(ReadOnlySpan<short> frame)
    {
        var bytes = new byte[frame.Length * sizeof(short)];
        Buffer.BlockCopy(frame.ToArray(), 0, bytes, 0, bytes.Length);
        var audioBase64 = Convert.ToBase64String(bytes);

        try
        {
            var response = _http.PostAsJsonAsync("/voice/wake-word/check", new { audio_base64 = audioBase64 })
                .GetAwaiter().GetResult();
            if (!response.IsSuccessStatusCode)
            {
                return false; // fail closed: an unavailable detector never falsely wakes
            }

            var result = response.Content.ReadFromJsonAsync<CheckResponse>().GetAwaiter().GetResult();
            return result?.Detected ?? false;
        }
        catch (HttpRequestException)
        {
            return false; // fail closed: an unreachable detector never falsely wakes
        }
    }
}

public sealed class HttpSpeechToText : ISpeechToText
{
    private sealed record TranscribeResponse([property: JsonPropertyName("text")] string Text);

    private readonly HttpClient _http;

    public HttpSpeechToText(HttpClient httpClient)
    {
        _http = httpClient;
    }

    public async Task<string> TranscribeAsync(ReadOnlyMemory<short> audio, int sampleRateHz, CancellationToken ct = default)
    {
        var samples = audio.ToArray();
        var bytes = new byte[samples.Length * sizeof(short)];
        Buffer.BlockCopy(samples, 0, bytes, 0, bytes.Length);

        var response = await _http.PostAsJsonAsync(
            "/voice/stt/transcribe",
            new { audio_base64 = Convert.ToBase64String(bytes), sample_rate = sampleRateHz },
            ct);
        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<TranscribeResponse>(cancellationToken: ct);
        return result?.Text ?? string.Empty;
    }
}
