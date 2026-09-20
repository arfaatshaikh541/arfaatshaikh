using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

public class VoiceCommandPhrasesTests
{
    [Theory]
    [InlineData("close your ears")]
    [InlineData("Close your ears.")]
    [InlineData("AURA, please stop listening now")]
    [InlineData("go to sleep")]
    public void Sleep_phrases_are_recognized(string text)
    {
        Assert.Equal(VoiceCommandPhrase.Sleep, VoiceCommandPhrases.TryMatch(text));
    }

    [Theory]
    [InlineData("shut down")]
    [InlineData("Please shut down.")]
    [InlineData("power off")]
    [InlineData("turn yourself off")]
    public void Shutdown_phrases_are_recognized(string text)
    {
        Assert.Equal(VoiceCommandPhrase.ShutDown, VoiceCommandPhrases.TryMatch(text));
    }

    [Theory]
    [InlineData("what's the weather today")]
    [InlineData("")]
    [InlineData("remind me to call Acme tomorrow")]
    public void Ordinary_speech_is_not_matched(string text)
    {
        Assert.Null(VoiceCommandPhrases.TryMatch(text));
    }
}
