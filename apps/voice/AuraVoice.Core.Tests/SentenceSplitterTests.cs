using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

public class SentenceSplitterTests
{
    [Fact]
    public void A_single_complete_sentence_in_one_chunk_is_returned_immediately()
    {
        var splitter = new SentenceSplitter();

        var sentences = splitter.Push("Hello there. ");

        Assert.Equal(new[] { "Hello there." }, sentences);
    }

    [Fact]
    public void An_incomplete_sentence_is_buffered_not_returned()
    {
        var splitter = new SentenceSplitter();

        var sentences = splitter.Push("Hello there");

        Assert.Empty(sentences);
    }

    [Fact]
    public void A_sentence_split_across_multiple_chunks_completes_once_the_boundary_arrives()
    {
        var splitter = new SentenceSplitter();

        var first = splitter.Push("The weather ");
        var second = splitter.Push("today is nice");
        var third = splitter.Push(". ");

        Assert.Empty(first);
        Assert.Empty(second);
        Assert.Equal(new[] { "The weather today is nice." }, third);
    }

    [Fact]
    public void Multiple_complete_sentences_in_one_chunk_are_all_returned_in_order()
    {
        var splitter = new SentenceSplitter();

        var sentences = splitter.Push("First one. Second one! Third one? ");

        Assert.Equal(new[] { "First one.", "Second one!", "Third one?" }, sentences);
    }

    [Fact]
    public void A_trailing_period_with_no_following_whitespace_yet_stays_buffered()
    {
        // Simulates a chunk boundary landing exactly after a period that
        // might actually be part of a decimal number ("3" | ".14") --
        // resolved only once more text (or Flush) arrives.
        var splitter = new SentenceSplitter();

        var sentences = splitter.Push("The value is 3.");

        Assert.Empty(sentences);
    }

    [Fact]
    public void Flush_returns_the_remaining_buffered_text()
    {
        var splitter = new SentenceSplitter();
        splitter.Push("An unfinished thought");

        var remainder = splitter.Flush();

        Assert.Equal("An unfinished thought", remainder);
    }

    [Fact]
    public void Flush_returns_null_when_nothing_is_buffered()
    {
        var splitter = new SentenceSplitter();
        splitter.Push("A complete sentence. ");

        var remainder = splitter.Flush();

        Assert.Null(remainder);
    }

    [Fact]
    public void Flush_after_a_split_sentence_only_returns_what_is_left_over()
    {
        var splitter = new SentenceSplitter();
        splitter.Push("Complete. Then trailing text with no punctuation");

        var remainder = splitter.Flush();

        Assert.Equal("Then trailing text with no punctuation", remainder);
    }
}
