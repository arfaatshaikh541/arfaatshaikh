using AuraShell.Core;
using Xunit;

namespace AuraShell.Core.Tests;

public class HotkeyDefinitionTests
{
    [Fact]
    public void Parse_reads_the_centralized_config_string_format()
    {
        var hotkey = HotkeyDefinition.Parse("Ctrl+Alt+Shift+A");

        Assert.NotNull(hotkey);
        Assert.True(hotkey!.Ctrl);
        Assert.True(hotkey.Alt);
        Assert.True(hotkey.Shift);
        Assert.False(hotkey.Win);
        Assert.Equal("A", hotkey.Key);
    }

    [Fact]
    public void Parse_is_case_and_order_insensitive_for_modifiers()
    {
        var hotkey = HotkeyDefinition.Parse("shift+CTRL+alt+A");

        Assert.NotNull(hotkey);
        Assert.True(hotkey!.Ctrl && hotkey.Alt && hotkey.Shift);
    }

    [Fact]
    public void Parse_supports_the_windows_key_modifier()
    {
        var hotkey = HotkeyDefinition.Parse("Win+Alt+D");

        Assert.NotNull(hotkey);
        Assert.True(hotkey!.Win);
    }

    [Fact]
    public void Parse_rejects_a_string_with_no_key_at_all()
    {
        Assert.Null(HotkeyDefinition.Parse("Ctrl+Alt"));
    }

    [Fact]
    public void Parse_rejects_a_string_with_two_non_modifier_tokens()
    {
        Assert.Null(HotkeyDefinition.Parse("Ctrl+A+B"));
    }

    [Fact]
    public void Parse_rejects_an_empty_string()
    {
        Assert.Null(HotkeyDefinition.Parse(""));
    }

    [Fact]
    public void ToString_round_trips_into_the_same_configuration_format()
    {
        var hotkey = new HotkeyDefinition(Ctrl: true, Alt: true, Shift: true, Win: false, Key: "A");

        Assert.Equal("Ctrl+Alt+Shift+A", hotkey.ToString());
    }
}

public class HotkeyDebouncerTests
{
    [Fact]
    public void The_first_press_always_fires()
    {
        var debouncer = new HotkeyDebouncer(TimeSpan.FromMilliseconds(300));

        Assert.True(debouncer.ShouldFire());
    }

    [Fact]
    public void A_second_press_inside_the_debounce_window_is_suppressed()
    {
        var now = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var debouncer = new HotkeyDebouncer(TimeSpan.FromMilliseconds(300), () => now);

        Assert.True(debouncer.ShouldFire());
        now = now.AddMilliseconds(50); // simulates a duplicate OS event / key-down+key-up race
        Assert.False(debouncer.ShouldFire());
    }

    [Fact]
    public void A_press_after_the_debounce_window_fires_again()
    {
        var now = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var debouncer = new HotkeyDebouncer(TimeSpan.FromMilliseconds(300), () => now);

        Assert.True(debouncer.ShouldFire());
        now = now.AddMilliseconds(500);
        Assert.True(debouncer.ShouldFire());
    }

    [Fact]
    public void Many_rapid_repeated_presses_only_fire_once()
    {
        var now = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var debouncer = new HotkeyDebouncer(TimeSpan.FromMilliseconds(300), () => now);

        var fireCount = 0;
        for (var i = 0; i < 20; i++)
        {
            if (debouncer.ShouldFire())
            {
                fireCount++;
            }
            now = now.AddMilliseconds(10);
        }

        Assert.Equal(1, fireCount);
    }

    [Fact]
    public void Reset_allows_an_immediate_fire_even_inside_the_window()
    {
        var now = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var debouncer = new HotkeyDebouncer(TimeSpan.FromMilliseconds(300), () => now);
        debouncer.ShouldFire();

        debouncer.Reset();

        Assert.True(debouncer.ShouldFire());
    }

    [Fact]
    public void A_negative_window_is_rejected_at_construction()
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => new HotkeyDebouncer(TimeSpan.FromMilliseconds(-1)));
    }
}
