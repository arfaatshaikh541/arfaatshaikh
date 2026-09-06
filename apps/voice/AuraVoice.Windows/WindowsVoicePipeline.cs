using AuraVoice.Core;

namespace AuraVoice.Windows;

/// <summary>
/// Wires the microphone, VAD, wake-word detector, STT, TTS, and the pure
/// VoiceSessionController together into the actual always-listening loop.
/// Real, structurally complete code — compiled successfully in this
/// session — but never executed against real audio (no microphone in this
/// build environment, and the wake-word/STT engines are NullXxx
/// placeholders until you wire in Porcupine/Vosk per apps/voice/README.md).
/// Silence-based end-of-utterance detection (SilenceFramesToEndUtterance)
/// is a reasonable starting heuristic, not a tuned constant — expect to
/// adjust it once real audio is flowing through this on real hardware.
/// </summary>
public sealed class WindowsVoicePipeline : IDisposable
{
    private const int SilenceFramesToEndUtterance = 25; // ~500ms at 20ms frames

    private readonly NAudioMicrophoneSource _microphone;
    private readonly IVoiceActivityDetector _vad;
    private readonly IWakeWordDetector _wakeWordDetector;
    private readonly ISpeechToText _speechToText;
    private readonly ITextToSpeech _textToSpeech;
    private readonly List<short> _utteranceBuffer = new();
    private int _consecutiveSilenceFrames;

    public VoiceSessionController Controller { get; } = new();

    public WindowsVoicePipeline(
        IWakeWordDetector wakeWordDetector,
        ISpeechToText speechToText,
        ITextToSpeech textToSpeech,
        IVoiceActivityDetector? vad = null,
        int sampleRateHz = 16000)
    {
        _wakeWordDetector = wakeWordDetector;
        _speechToText = speechToText;
        _textToSpeech = textToSpeech;
        _vad = vad ?? new EnergyVoiceActivityDetector();
        _microphone = new NAudioMicrophoneSource(sampleRateHz);
        _microphone.FrameCaptured += OnFrameCaptured;
    }

    public void Start()
    {
        Controller.StartWakeListening();
        _microphone.Start();
    }

    public void Stop()
    {
        _microphone.Stop();
        Controller.Sleep();
    }

    private void OnFrameCaptured(short[] frame)
    {
        switch (Controller.State)
        {
            case VoiceState.ListeningForWake:
                if (_wakeWordDetector.ProcessFrame(frame))
                {
                    Controller.OnWakeWordDetected();
                }
                break;

            case VoiceState.Awake:
                HandleAwakeFrame(frame);
                break;

            case VoiceState.Speaking:
                // Barge-in: the owner started talking over AURA.
                if (_vad.IsSpeech(frame))
                {
                    _textToSpeech.Stop();
                    Controller.OnBargeIn();
                }
                break;

            case VoiceState.Idle:
            case VoiceState.Processing:
                break; // not listening for new audio in these states
        }
    }

    private void HandleAwakeFrame(short[] frame)
    {
        if (_vad.IsSpeech(frame))
        {
            _utteranceBuffer.AddRange(frame);
            _consecutiveSilenceFrames = 0;
            return;
        }

        if (_utteranceBuffer.Count == 0)
        {
            return; // still waiting for the owner to start talking
        }

        _consecutiveSilenceFrames++;
        if (_consecutiveSilenceFrames < SilenceFramesToEndUtterance)
        {
            _utteranceBuffer.AddRange(frame); // keep a little trailing silence in the clip
            return;
        }

        var audio = _utteranceBuffer.ToArray();
        _utteranceBuffer.Clear();
        _consecutiveSilenceFrames = 0;
        _ = TranscribeAndCaptureAsync(audio);
    }

    private async Task TranscribeAndCaptureAsync(short[] audio)
    {
        var text = await _speechToText.TranscribeAsync(audio, sampleRateHz: 16000);
        if (!string.IsNullOrWhiteSpace(text))
        {
            Controller.OnCommandCaptured(text);
        }
    }

    public void Dispose() => _microphone.Dispose();
}
