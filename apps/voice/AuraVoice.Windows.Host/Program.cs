using System.Text;
using AuraShell.Core;
using AuraVoice.Core;
using AuraVoice.Windows;

// The real, runnable voice assistant: microphone -> VAD -> wake-word ->
// streaming STT -> aura_core reasoning/action -> TTS -> barge-in, all
// wired together from genuinely tested pieces (WindowsVoicePipeline,
// ConversationOrchestrator, the Http* provider adapters, and the same
// AuraApiClient the WPF shell uses). Every provider here is swappable —
// AURA_VOICE_TTS_ENGINE picks between the local sherpa-onnx/Piper voice
// (served by aura_core, consistent everywhere) and Windows' built-in SAPI
// voice — exactly the "local provider now, alternatives later" shape
// requested for this pipeline. See apps/voice/README.md for exactly what
// is and isn't verified without a real Windows machine.

var coreSocketPath = Environment.GetEnvironmentVariable("AURA_CORE_SOCKET");
var coreUrl = Environment.GetEnvironmentVariable("AURA_CORE_URL") ?? "http://127.0.0.1:8000";
var deviceToken = Environment.GetEnvironmentVariable("AURA_DEVICE_TOKEN");
var ttsEngine = Environment.GetEnvironmentVariable("AURA_VOICE_TTS_ENGINE") ?? "local";
var conversationWindowSeconds = double.TryParse(
    Environment.GetEnvironmentVariable("AURA_VOICE_CONVERSATION_WINDOW_SECONDS"), out var seconds)
    ? seconds
    : 8.0;
var logPath = Environment.GetEnvironmentVariable("AURA_VOICE_LOG_FILE")
    ?? System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AURA", "logs", "voice.log");

using var log = new FileVoiceLog(logPath);
// AURA_CORE_SOCKET (a Unix domain socket path, printed by `aura serve`
// on startup) is the section-7 "local, not localhost" transport and
// takes priority when set; AURA_CORE_URL is the loopback-TCP fallback.
// AURA_DEVICE_TOKEN (saved by `aura enroll`) is attached to every
// request once set, so this host keeps working uninterrupted once
// enrollment turns on the core API's device-trust gate.
static HttpClient CreateCoreHttpClient(string? socketPath, string coreUrl, string? deviceToken)
{
    if (socketPath is not null)
    {
        return AuraShell.Core.IpcHttpClientFactory.CreateForSocket(socketPath, deviceToken);
    }
    var client = new HttpClient { BaseAddress = new Uri(coreUrl) };
    AuraShell.Core.DeviceTokenHeader.AttachIfConfigured(client, deviceToken);
    return client;
}

using var httpClient = CreateCoreHttpClient(coreSocketPath, coreUrl, deviceToken);
var apiClient = new AuraApiClient(httpClient);
var coreEndpointDescription = coreSocketPath is not null ? $"unix socket {coreSocketPath}" : coreUrl;

log.Info($"AURA voice host starting. aura_core at {coreEndpointDescription}, TTS engine: {ttsEngine}, log file: {logPath}");
if (!await apiClient.IsHealthyAsync())
{
    log.Warn(
        $"aura_core is not reachable at {coreEndpointDescription} right now. The wake-word/STT providers below " +
        "fail closed (never falsely trigger) when they can't reach it, so voice input will " +
        "simply do nothing rather than misbehave until it's back.");
}

var wakeWordDetector = new HttpWakeWordDetector(httpClient);
var speechToText = new HttpSpeechToText(httpClient);

ITextToSpeech textToSpeech = ttsEngine.Equals("sapi", StringComparison.OrdinalIgnoreCase)
    ? new SapiTextToSpeech()
    : new HttpTextToSpeech(httpClient);

using var pipeline = new WindowsVoicePipeline(wakeWordDetector, speechToText, textToSpeech);

async Task<string> GenerateResponseAsync(string message, CancellationToken ct)
{
    var response = new StringBuilder();
    await foreach (var evt in apiClient.ChatStreamAsync(message, ct))
    {
        switch (evt.Event)
        {
            case "chunk":
                response.Append(evt.Data);
                break;
            case "error":
                response.Append($" (error: {evt.Data})");
                break;
        }
    }
    return response.ToString();
}

using var orchestrator = new ConversationOrchestrator(
    pipeline.Controller, GenerateResponseAsync, textToSpeech,
    conversationWindow: TimeSpan.FromSeconds(conversationWindowSeconds));

pipeline.Controller.StateChanged += state => log.Info($"state -> {state}");
orchestrator.ResponseSpoken += response => log.Info($"aura: {response}");
orchestrator.ResponseFailed += ex => log.Error("response generation failed", ex);

var shutdownRequested = new TaskCompletionSource();
orchestrator.ShutdownRequested += () =>
{
    log.Info("Shutdown phrase recognized -- stopping.");
    shutdownRequested.TrySetResult();
};

pipeline.Start();
log.Info("Listening for the wake word. Press Enter, or say \"shut down\", to stop.");

var consoleReadLine = Task.Run(() => Console.ReadLine());
await Task.WhenAny(consoleReadLine, shutdownRequested.Task);

pipeline.Stop();
if (textToSpeech is IDisposable disposableTts)
{
    disposableTts.Dispose();
}
log.Info("AURA voice host stopped.");
