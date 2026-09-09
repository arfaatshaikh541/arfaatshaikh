using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

public class HttpWakeWordDetectorTests
{
    [Fact]
    public void ProcessFrame_sends_base64_encoded_pcm16_and_returns_detected_flag()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/voice/wake-word/check", """{"score": 0.91, "detected": true}""");
        var detector = new HttpWakeWordDetector(new HttpClient(handler) { BaseAddress = new Uri("http://fake.local") });

        short[] frame = { 100, -100, 200, -200 };
        var result = detector.ProcessFrame(frame);

        Assert.True(result);
        var body = Assert.Single(handler.RequestBodies);
        Assert.Contains("audio_base64", body);
    }

    [Fact]
    public void ProcessFrame_fails_closed_when_the_server_is_unreachable()
    {
        var detector = new HttpWakeWordDetector(new HttpClient(new ThrowingHandler()) { BaseAddress = new Uri("http://fake.local") });

        var result = detector.ProcessFrame(new short[] { 1, 2, 3 });

        Assert.False(result); // never falsely wakes when the detector can't be reached
    }

    [Fact]
    public void ProcessFrame_returns_false_when_score_is_below_threshold()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/voice/wake-word/check", """{"score": 0.02, "detected": false}""");
        var detector = new HttpWakeWordDetector(new HttpClient(handler) { BaseAddress = new Uri("http://fake.local") });

        Assert.False(detector.ProcessFrame(new short[] { 1, 2, 3 }));
    }

    private sealed class ThrowingHandler : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => throw new HttpRequestException("simulated connection failure");
    }
}

public class HttpSpeechToTextTests
{
    [Fact]
    public async Task TranscribeAsync_sends_audio_and_sample_rate_and_returns_text()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/voice/stt/transcribe", """{"text": "open the door please"}""");
        var stt = new HttpSpeechToText(new HttpClient(handler) { BaseAddress = new Uri("http://fake.local") });

        var text = await stt.TranscribeAsync(new short[] { 1, 2, 3, 4 }, sampleRateHz: 16000);

        Assert.Equal("open the door please", text);
        var body = Assert.Single(handler.RequestBodies);
        Assert.Contains("\"sample_rate\":16000", body);
    }

    [Fact]
    public async Task TranscribeAsync_returns_empty_string_when_response_has_no_text_field()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapJson(HttpMethod.Post, "/voice/stt/transcribe", "{}");
        var stt = new HttpSpeechToText(new HttpClient(handler) { BaseAddress = new Uri("http://fake.local") });

        var text = await stt.TranscribeAsync(new short[] { 1 }, sampleRateHz: 16000);

        Assert.Equal(string.Empty, text);
    }
}
