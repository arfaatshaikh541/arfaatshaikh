using System.Text;

namespace AuraVoice.Core;

/// <summary>
/// Incremental sentence-boundary detector for streamed model text. This
/// exists because neither the STT (Whisper via sherpa-onnx, an offline
/// encoder-decoder architecture) nor the TTS (Piper/VITS via
/// sherpa-onnx, a full-utterance vocoder) in this build has a genuine
/// incremental/streaming inference mode -- there is no "streaming
/// Whisper" or "streaming Piper" to switch on, only a different model
/// architecture entirely (a streaming transducer for STT, a streaming
/// vocoder for TTS), which this build does not have credentials-free
/// access to download and has not adopted. The achievable, honest
/// approximation of "streaming" for the text-to-speech side is this:
/// speak each sentence of the reply as soon as the model has finished
/// producing it, rather than waiting for the entire reply -- a real
/// latency improvement that needs no new model.
///
/// Deliberately a simple heuristic (./!/? followed by whitespace), not
/// real NLP sentence segmentation -- "Dr. Smith" or "3.14" can split
/// early. That is an acceptable trade for a voice assistant's short,
/// conversational replies, where speaking a sentence fragment slightly
/// early is far less costly than the latency of waiting for the whole
/// reply.
/// </summary>
public sealed class SentenceSplitter
{
    private readonly StringBuilder _buffer = new();

    /// <summary>Feeds newly arrived text. Returns any sentences that are
    /// now complete (zero, one, or more, if a single chunk contains
    /// several) -- text after the last detected boundary stays buffered
    /// for the next call.</summary>
    public IReadOnlyList<string> Push(string chunk)
    {
        _buffer.Append(chunk);
        var text = _buffer.ToString();
        var sentences = new List<string>();
        var start = 0;

        for (var i = 0; i < text.Length; i++)
        {
            if (text[i] is not ('.' or '!' or '?'))
            {
                continue;
            }
            // Only a boundary if followed by whitespace already in the
            // buffer -- a punctuation mark at the very end of what's
            // arrived so far might just be a chunk boundary mid-sentence
            // ("...the answer is 3" | ".14"), so it stays buffered until
            // either more text or Flush() resolves it.
            if (i + 1 < text.Length && char.IsWhiteSpace(text[i + 1]))
            {
                var sentence = text[start..(i + 1)].Trim();
                if (sentence.Length > 0)
                {
                    sentences.Add(sentence);
                }
                start = i + 1;
            }
        }

        _buffer.Clear();
        _buffer.Append(text[start..]);
        return sentences;
    }

    /// <summary>Call once the stream has ended -- returns whatever text
    /// remains buffered (a final sentence with no trailing punctuation,
    /// or null if nothing is left).</summary>
    public string? Flush()
    {
        var remainder = _buffer.ToString().Trim();
        _buffer.Clear();
        return remainder.Length > 0 ? remainder : null;
    }
}
