using System.Net.Http.Json;
using AuraVoice.Core;
using NAudio.Wave;

namespace AuraVoice.Windows;

/// <summary>
/// Text-to-speech backed by the aura_core HTTP API's /voice/tts/speak
/// endpoint (real sherpa-onnx/Piper synthesis on the Python side),
/// played back via NAudio — real code, not run against a real speaker in
/// this session (no audio output device here; see apps/voice/README.md).
/// An alternative to SapiTextToSpeech: this one produces AURA's actual
/// configured voice (consistent across platforms, since it's the same
/// Python model everywhere) rather than whatever voice Windows SAPI has
/// installed.
/// </summary>
public sealed class HttpTextToSpeech : ITextToSpeech, IDisposable
{
    private readonly HttpClient _http;
    private WaveOutEvent? _currentOutput;

    public HttpTextToSpeech(HttpClient httpClient)
    {
        _http = httpClient;
    }

    public async Task SpeakAsync(string text, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync("/voice/tts/speak", new { text }, ct);
        response.EnsureSuccessStatusCode();
        var wavBytes = await response.Content.ReadAsByteArrayAsync(ct);

        using var stream = new MemoryStream(wavBytes);
        using var reader = new WaveFileReader(stream);
        using var output = new WaveOutEvent();
        _currentOutput = output;

        var completed = new TaskCompletionSource();
        void OnPlaybackStopped(object? sender, StoppedEventArgs e) => completed.TrySetResult();
        output.PlaybackStopped += OnPlaybackStopped;

        using var registration = ct.Register(() => output.Stop());
        try
        {
            output.Init(reader);
            output.Play();
            await completed.Task;
        }
        finally
        {
            output.PlaybackStopped -= OnPlaybackStopped;
            _currentOutput = null;
        }
    }

    public void Stop() => _currentOutput?.Stop();

    public void Dispose() => _currentOutput?.Dispose();
}
