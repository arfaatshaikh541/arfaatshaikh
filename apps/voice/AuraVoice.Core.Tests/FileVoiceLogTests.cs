using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

public class FileVoiceLogTests
{
    [Fact]
    public void Info_warn_and_error_lines_are_actually_written_to_the_file()
    {
        var path = System.IO.Path.Combine(Path.GetTempPath(), $"aura_voice_log_{Guid.NewGuid():N}.log");
        try
        {
            using (var log = new FileVoiceLog(path, echoToConsole: false))
            {
                log.Info("wake word model loaded");
                log.Warn("aura_core unreachable, retrying");
                log.Error("speech-to-text call failed", new InvalidOperationException("boom"));
            }

            var lines = File.ReadAllLines(path);
            Assert.Equal(3, lines.Length);
            Assert.Contains("[INFO]", lines[0]);
            Assert.Contains("wake word model loaded", lines[0]);
            Assert.Contains("[WARN]", lines[1]);
            Assert.Contains("[ERROR]", lines[2]);
            Assert.Contains("boom", lines[2]); // the real exception's message, not swallowed
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void Creates_missing_parent_directories()
    {
        var directory = System.IO.Path.Combine(Path.GetTempPath(), $"aura_voice_log_dir_{Guid.NewGuid():N}");
        var path = System.IO.Path.Combine(directory, "voice.log");
        try
        {
            using var log = new FileVoiceLog(path, echoToConsole: false);
            log.Info("hello");
            Assert.True(File.Exists(path));
        }
        finally
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
    }

    [Fact]
    public void Appends_across_multiple_instances_rather_than_truncating()
    {
        var path = System.IO.Path.Combine(Path.GetTempPath(), $"aura_voice_log_append_{Guid.NewGuid():N}.log");
        try
        {
            using (var first = new FileVoiceLog(path, echoToConsole: false))
            {
                first.Info("first line");
            }
            using (var second = new FileVoiceLog(path, echoToConsole: false))
            {
                second.Info("second line");
            }

            var lines = File.ReadAllLines(path);
            Assert.Equal(2, lines.Length);
            Assert.Contains("first line", lines[0]);
            Assert.Contains("second line", lines[1]);
        }
        finally
        {
            File.Delete(path);
        }
    }
}
