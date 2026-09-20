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
    private readonly int _sampleRateHz;
    private readonly int _frameMilliseconds;
    private WaveInEvent _waveIn;
    private bool _stoppedDeliberately;
    private int _consecutiveReopenFailures;
    private CancellationTokenSource? _reopenCts;

    public event Action<short[]>? FrameCaptured;

    /// <summary>Fired when the device stopped on its own (unplugged,
    /// driver reset, Bluetooth dropout) rather than because Stop() was
    /// called -- see OnRecordingStopped. A future diagnostics view can
    /// surface this; today it is at least logged by whichever host
    /// process owns this pipeline (see AuraVoice.Windows.Host).</summary>
    public event Action<Exception>? DeviceLost;

    /// <summary>Fired after DeviceLost, once a reopen attempt actually
    /// succeeds -- the real "self-healing without reinstall" signal
    /// (section 17), not just a log line nobody reads.</summary>
    public event Action? DeviceRecovered;

    public bool IsRunning { get; private set; }

    public NAudioMicrophoneSource(int sampleRateHz = 16000, int frameMilliseconds = 20)
    {
        _sampleRateHz = sampleRateHz;
        _frameMilliseconds = frameMilliseconds;
        _waveIn = CreateWaveIn();
    }

    private WaveInEvent CreateWaveIn()
    {
        var waveIn = new WaveInEvent
        {
            WaveFormat = new WaveFormat(_sampleRateHz, 16, 1),
            BufferMilliseconds = _frameMilliseconds,
        };
        waveIn.DataAvailable += OnDataAvailable;
        waveIn.RecordingStopped += OnRecordingStopped;
        return waveIn;
    }

    /// <summary>Idempotent -- calling Start() while already running is a
    /// no-op rather than NAudio's own "already recording" exception, so
    /// callers (WindowsVoicePipeline reacting to privacy-mode changes,
    /// the reopen-after-device-loss path below) never need to track
    /// hardware state themselves on top of this class's.</summary>
    public void Start()
    {
        // An explicit Start() always supersedes any in-flight automatic
        // reopen attempt (e.g. one still backing off after a very recent
        // device loss) -- the caller's authoritative intent wins, and the
        // reopen loop's own upcoming Start() call becomes a no-op once it
        // sees IsRunning already true.
        CancelPendingReopen();
        if (IsRunning)
        {
            return;
        }
        _stoppedDeliberately = false;
        _waveIn.StartRecording();
        IsRunning = true;
    }

    public void Stop()
    {
        // Always cancel a pending automatic reopen, even if IsRunning is
        // already false (the device may have died and be mid-backoff
        // when this is called) -- otherwise a reopen could physically
        // switch the microphone back on after the caller explicitly
        // asked for it to be off (e.g. FullMicOff privacy mode, or the
        // pipeline being stopped entirely).
        CancelPendingReopen();
        _stoppedDeliberately = true;
        if (!IsRunning)
        {
            return;
        }
        _waveIn.StopRecording();
        IsRunning = false;
    }

    private void CancelPendingReopen()
    {
        _reopenCts?.Cancel();
        _reopenCts?.Dispose();
        _reopenCts = null;
    }

    private void OnDataAvailable(object? sender, WaveInEventArgs e)
    {
        var sampleCount = e.BytesRecorded / sizeof(short);
        var samples = new short[sampleCount];
        Buffer.BlockCopy(e.Buffer, 0, samples, 0, e.BytesRecorded);
        FrameCaptured?.Invoke(samples);
    }

    /// <summary>
    /// NAudio raises RecordingStopped both for a deliberate Stop() call
    /// (Exception is null) and for the device genuinely disappearing out
    /// from under it -- unplugged, a Bluetooth dropout, a driver reset,
    /// or a default-device change that invalidates the open handle
    /// (Exception is non-null). Only the second case is a real fault:
    /// this reopens the device with a short exponential backoff,
    /// capped, rather than either silently going deaf forever or
    /// spinning tightly against a device that is genuinely gone (e.g.
    /// physically unplugged and not coming back). IsRunning is reset
    /// first so a caller's own Start()/Stop() calls made from a
    /// DeviceLost handler are never treated as a no-op by mistake.
    /// </summary>
    private void OnRecordingStopped(object? sender, StoppedEventArgs e)
    {
        IsRunning = false;
        if (_stoppedDeliberately || e.Exception is null)
        {
            return;
        }

        DeviceLost?.Invoke(e.Exception);
        _reopenCts?.Cancel();
        _reopenCts?.Dispose();
        var cts = new CancellationTokenSource();
        _reopenCts = cts;
        _ = AttemptReopenAsync(cts.Token);
    }

    private static readonly TimeSpan[] ReopenBackoff =
    {
        TimeSpan.FromMilliseconds(500),
        TimeSpan.FromSeconds(2),
        TimeSpan.FromSeconds(5),
        TimeSpan.FromSeconds(15),
        TimeSpan.FromSeconds(30), // then holds here -- never gives up permanently
    };

    private async Task AttemptReopenAsync(CancellationToken ct)
    {
        var delay = ReopenBackoff[Math.Min(_consecutiveReopenFailures, ReopenBackoff.Length - 1)];
        try
        {
            await Task.Delay(delay, ct);
        }
        catch (OperationCanceledException)
        {
            return; // Stop()/Start() superseded this attempt -- see CancelPendingReopen
        }

        if (ct.IsCancellationRequested)
        {
            return;
        }

        try
        {
            _waveIn.DataAvailable -= OnDataAvailable;
            _waveIn.RecordingStopped -= OnRecordingStopped;
            _waveIn.Dispose();
            _waveIn = CreateWaveIn();
            if (ct.IsCancellationRequested)
            {
                return; // superseded while we were swapping the device handle
            }
            _stoppedDeliberately = false;
            _waveIn.StartRecording();
            IsRunning = true;
            _consecutiveReopenFailures = 0;
            _reopenCts = null;
            DeviceRecovered?.Invoke();
        }
        catch (Exception)
        {
            // Still gone (unplugged and not reconnected yet, or the OS
            // hasn't finished re-enumerating it) -- back off further and
            // try again rather than surfacing a crash for a transient,
            // externally-caused hardware state.
            _consecutiveReopenFailures++;
            if (!ct.IsCancellationRequested)
            {
                _ = AttemptReopenAsync(ct);
            }
        }
    }

    public void Dispose()
    {
        CancelPendingReopen();
        _waveIn.DataAvailable -= OnDataAvailable;
        _waveIn.RecordingStopped -= OnRecordingStopped;
        _waveIn.Dispose();
    }
}
