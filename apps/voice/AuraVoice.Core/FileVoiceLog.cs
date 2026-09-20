namespace AuraVoice.Core;

/// <summary>
/// The voice pipeline's own operational log -- separate from aura_core's
/// hash-chained governance Audit Log (which records action decisions, not
/// "the wake-word model failed to load" or "aura_core was unreachable for
/// 3 seconds"). Appends timestamped, leveled lines to a real file on disk
/// so a person debugging a bad session on their own machine has something
/// to look at (and something to attach to a support request) beyond
/// whatever scrolled past in the console.
/// </summary>
public interface IVoiceLog
{
    void Info(string message);
    void Warn(string message);
    void Error(string message, Exception? exception = null);
}

public sealed class FileVoiceLog : IVoiceLog, IDisposable
{
    private readonly StreamWriter _writer;
    private readonly bool _echoToConsole;
    private readonly object _lock = new();

    public string Path { get; }

    public FileVoiceLog(string path, bool echoToConsole = true)
    {
        Path = System.IO.Path.GetFullPath(path);
        var directory = System.IO.Path.GetDirectoryName(Path);
        if (!string.IsNullOrEmpty(directory))
        {
            Directory.CreateDirectory(directory);
        }
        _writer = new StreamWriter(new FileStream(Path, FileMode.Append, FileAccess.Write, FileShare.Read))
        {
            AutoFlush = true,
        };
        _echoToConsole = echoToConsole;
    }

    public void Info(string message) => Write("INFO", message);
    public void Warn(string message) => Write("WARN", message);

    public void Error(string message, Exception? exception = null) =>
        Write("ERROR", exception is null ? message : $"{message}: {exception}");

    private void Write(string level, string message)
    {
        var line = $"{DateTime.UtcNow:O} [{level}] {message}";
        lock (_lock)
        {
            _writer.WriteLine(line);
        }
        if (_echoToConsole)
        {
            Console.WriteLine(line);
        }
    }

    public void Dispose() => _writer.Dispose();
}
