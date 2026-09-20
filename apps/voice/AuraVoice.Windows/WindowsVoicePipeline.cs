using AuraVoice.Core;

namespace AuraVoice.Windows;

/// <summary>
/// Wires the microphone, VAD, wake-word detector, STT, TTS, and the pure
/// VoiceSessionController together into the actual always-listening loop.
/// AuraVoice.Windows.Host is the composition root that constructs this
/// with the real, wired-in providers (HttpWakeWordDetector/HttpSpeechToText
/// backed by aura_core's local openWakeWord/sherpa-onnx models, plus
/// ConversationOrchestrator for the reasoning round-trip and conversation
/// timeout) — see apps/voice/README.md. Real, structurally complete code —
/// compiled successfully in this session — but never executed against
/// real audio, since there is no microphone in this build environment.
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
    private bool _started;

    public VoiceSessionController Controller { get; } = new();

    /// <summary>The real gate behind the "FULL MIC OFF vs. WAKE-WORD-ONLY"
    /// distinction (section 17) -- see VoicePrivacyGate's own docs. This
    /// pipeline is the one place that actually opens/closes the real
    /// NAudio device and decides whether a wake-word hit may proceed, in
    /// direct response to this gate's state.</summary>
    public VoicePrivacyGate PrivacyGate { get; } = new();

    /// <summary>Pass-through of NAudioMicrophoneSource's own device-loss
    /// signal (section 17's "self-healing without reinstall") -- the
    /// composition root (AuraVoice.Windows.Host) is what actually has
    /// somewhere to log it.</summary>
    public event Action<Exception>? MicrophoneDeviceLost;

    public event Action? MicrophoneDeviceRecovered;

    /// <summary>True exactly when the real hardware is open right now --
    /// false both for FullMicOff and for a device-loss window before
    /// reconnection succeeds.</summary>
    public bool IsMicrophoneOpen => _microphone.IsRunning;

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
        _microphone.DeviceLost += ex => MicrophoneDeviceLost?.Invoke(ex);
        _microphone.DeviceRecovered += () => MicrophoneDeviceRecovered?.Invoke();
        PrivacyGate.ModeChanged += OnPrivacyModeChanged;
    }

    public void Start()
    {
        _started = true;
        Controller.StartWakeListening();
        if (!PrivacyGate.RequiresMicrophoneOff)
        {
            _microphone.Start();
        }
    }

    public void Stop()
    {
        _started = false;
        _microphone.Stop();
        Controller.Sleep();
    }

    /// <summary>
    /// Reacts to a real privacy-mode change (pushed from aura_core -- see
    /// AuraVoice.Windows.Host's polling loop) by actually opening or
    /// closing the microphone hardware, not merely updating a flag that
    /// only a UI reads. FullMicOff physically stops capture; leaving it
    /// (to Normal or WakeWordOnly) reopens the device, since both of
    /// those need real audio flowing for wake-word detection to mean
    /// anything. A no-op while the pipeline itself hasn't been Start()ed
    /// yet -- Start() re-checks PrivacyGate.RequiresMicrophoneOff itself.
    /// </summary>
    private void OnPrivacyModeChanged(VoicePrivacyMode _)
    {
        if (!_started)
        {
            return;
        }

        if (PrivacyGate.RequiresMicrophoneOff)
        {
            _microphone.Stop();
            Controller.Sleep();
        }
        else
        {
            _microphone.Start();
            Controller.StartWakeListening();
        }
    }

    private void OnFrameCaptured(short[] frame)
    {
        switch (Controller.State)
        {
            case VoiceState.ListeningForWake:
                // WakeWordOnly still runs the detector for real (the mic
                // is genuinely open and processing) but a hit is
                // discarded rather than escalated -- there is no state
                // where the assistant is "muted" yet still acts on a
                // captured command. See VoicePrivacyGate's docs.
                if (_wakeWordDetector.ProcessFrame(frame) && PrivacyGate.AllowsWakeWordActivation)
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
