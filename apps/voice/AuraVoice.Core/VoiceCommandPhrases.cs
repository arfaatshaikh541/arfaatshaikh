namespace AuraVoice.Core;

/// <summary>Explicit owner-control phrases the product spec calls out by
/// name: "close your ears" / "stop listening" must quiet the microphone
/// without killing the process, and "shut down" must actually end it.
/// Before this, recognized speech went straight to the reasoning call
/// with no special-casing at all -- meaning saying "stop listening"
/// would have been sent to the model as a question, not obeyed.</summary>
public enum VoiceCommandPhrase
{
    Sleep,
    ShutDown,
}

public static class VoiceCommandPhrases
{
    private static readonly (string Phrase, VoiceCommandPhrase Command)[] Phrases = new[]
    {
        ("close your ears", VoiceCommandPhrase.Sleep),
        ("stop listening", VoiceCommandPhrase.Sleep),
        ("go to sleep", VoiceCommandPhrase.Sleep),
        ("stop listening to me", VoiceCommandPhrase.Sleep),
        ("shut down", VoiceCommandPhrase.ShutDown),
        ("power off", VoiceCommandPhrase.ShutDown),
        ("shut yourself down", VoiceCommandPhrase.ShutDown),
        ("turn yourself off", VoiceCommandPhrase.ShutDown),
    };

    /// <summary>Null when the utterance isn't a recognized control
    /// phrase -- the normal reasoning path handles it instead. Matches
    /// on containment (not just exact equality) so "AURA, please stop
    /// listening now" still matches "stop listening".</summary>
    public static VoiceCommandPhrase? TryMatch(string text)
    {
        var normalized = Normalize(text);
        if (normalized.Length == 0)
        {
            return null;
        }

        foreach (var (phrase, command) in Phrases)
        {
            if (normalized.Contains(phrase))
            {
                return command;
            }
        }
        return null;
    }

    private static string Normalize(string text) =>
        text.Trim().ToLowerInvariant().TrimEnd('.', '!', '?', ' ');
}
