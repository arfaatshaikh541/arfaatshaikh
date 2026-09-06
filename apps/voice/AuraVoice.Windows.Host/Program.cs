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

var coreUrl = Environment.GetEnvironmentVariable("AURA_CORE_URL") ?? "http://127.0.0.1:8000";
var ttsEngine = Environment.GetEnvironmentVariable("AURA_VOICE_TTS_ENGINE") ?? "local";
var conversationWindowSeconds = double.TryParse(
    Environment.GetEnvironmentVariable("AURA_VOICE_CONVERSATION_WINDOW_SECONDS"), out var seconds)
    ? seconds
    : 8.0;

using var httpClient = new HttpClient { BaseAddress = new Uri(coreUrl) };
var apiClient = new AuraApiClient(httpClient);

Console.WriteLine($"AURA voice host starting. aura_core at {coreUrl}, TTS engine: {ttsEngine}");
if (!await apiClient.IsHealthyAsync())
{
    Console.Error.WriteLine(
        $"WARNING: aura_core is not reachable at {coreUrl} right now. The wake-word/STT " +
        "providers below fail closed (never falsely trigger) when they can't reach it, so " +
        "voice input will simply do nothing rather than misbehave until it's back.");
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

pipeline.Controller.StateChanged += state => Console.WriteLine($"[voice] state -> {state}");
orchestrator.ResponseSpoken += response => Console.WriteLine($"[voice] aura: {response}");
orchestrator.ResponseFailed += ex => Console.Error.WriteLine($"[voice] response generation failed: {ex.Message}");

pipeline.Start();
Console.WriteLine("Listening for the wake word. Press Enter to stop.");
Console.ReadLine();

pipeline.Stop();
if (textToSpeech is IDisposable disposableTts)
{
    disposableTts.Dispose();
}
