using NAudio.Wave;

namespace AuraVoice.Windows;

/// <summary>
/// Captures 16-bit mono PCM from the default input device via NAudio.
/// Real code against NAudio's actual API — compiled successfully in this
/// session — but never run against a real microphone here (no audio
/// hardware in this build environment). See apps/voice/README.md.
/// </summary>
public sealed class NAudioMicrophoneSource : IDisposable
{
    private readonly WaveInEvent _waveIn;

    public event Action<short[]>? FrameCaptured;

    public NAudioMicrophoneSource(int sampleRateHz = 16000, int frameMilliseconds = 20)
    {
        _waveIn = new WaveInEvent
        {
            WaveFormat = new WaveFormat(sampleRateHz, 16, 1),
            BufferMilliseconds = frameMilliseconds,
        };
        _waveIn.DataAvailable += OnDataAvailable;
    }

    public void Start() => _waveIn.StartRecording();

    public void Stop() => _waveIn.StopRecording();

    private void OnDataAvailable(object? sender, WaveInEventArgs e)
    {
        var sampleCount = e.BytesRecorded / sizeof(short);
        var samples = new short[sampleCount];
        Buffer.BlockCopy(e.Buffer, 0, samples, 0, e.BytesRecorded);
        FrameCaptured?.Invoke(samples);
    }

    public void Dispose()
    {
        _waveIn.DataAvailable -= OnDataAvailable;
        _waveIn.Dispose();
    }
}
