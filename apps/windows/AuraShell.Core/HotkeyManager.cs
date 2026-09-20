namespace AuraShell.Core;

/// <summary>
/// A hotkey combination, expressed independent of any particular OS
/// registration API -- Ctrl+Alt+Shift+A is "Modifiers: Ctrl, Alt, Shift"
/// plus "Key: A", not a raw virtual-key code baked into UI code. See
/// docs/VOICE_FIRST_SECURE_INTERFACE.md#hotkey-collision-audit for why
/// this specific combination was chosen as AURA's default.
/// </summary>
public sealed record HotkeyDefinition(bool Ctrl, bool Alt, bool Shift, bool Win, string Key)
{
    public override string ToString()
    {
        var parts = new List<string>();
        if (Ctrl) parts.Add("Ctrl");
        if (Alt) parts.Add("Alt");
        if (Shift) parts.Add("Shift");
        if (Win) parts.Add("Win");
        parts.Add(Key);
        return string.Join("+", parts);
    }

    /// <summary>Parses the centralized config string format
    /// ("Ctrl+Alt+Shift+A") that aura_core's /interface/config endpoint
    /// serves, so the literal combination lives in exactly one place
    /// (the Python config) rather than being duplicated as a hardcoded
    /// default here. Returns null for a string that doesn't parse --
    /// callers must treat that as "no valid hotkey configured," never
    /// guess at what was meant.</summary>
    public static HotkeyDefinition? Parse(string text)
    {
        var parts = text.Split('+', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0)
        {
            return null;
        }

        bool ctrl = false, alt = false, shift = false, win = false;
        string? key = null;
        foreach (var part in parts)
        {
            switch (part.ToLowerInvariant())
            {
                case "ctrl": case "control": ctrl = true; break;
                case "alt": alt = true; break;
                case "shift": shift = true; break;
                case "win": case "windows": win = true; break;
                default:
                    if (key is not null)
                    {
                        return null; // more than one non-modifier token -- not a valid single hotkey
                    }
                    key = part;
                    break;
            }
        }

        return key is null ? null : new HotkeyDefinition(ctrl, alt, shift, win, key);
    }
}

public enum HotkeyRegistrationStatus
{
    Registered,
    AlreadyInUse,
    Unsupported,
    Failed,
}

public sealed record HotkeyRegistrationResult(HotkeyRegistrationStatus Status, string? Detail = null)
{
    public bool Succeeded => Status == HotkeyRegistrationStatus.Registered;
}

/// <summary>
/// Platform-independent hotkey registration contract (section 38's
/// "InputChannel"-style abstraction: business logic never talks to
/// Win32 directly). The concrete Windows implementation
/// (Win32HotkeyManager, in the AuraShell WPF project) needs a real
/// window handle and the Windows message loop, so it cannot be built or
/// exercised in a non-Windows environment -- REQUIRES_WINDOWS_RUNTIME,
/// same as every other native-Windows-API surface in this codebase.
/// What CAN be built and tested anywhere is this interface plus the
/// debounce/dedup logic in HotkeyDebouncer below, which every concrete
/// implementation is expected to use.
/// </summary>
public interface IHotkeyManager : IDisposable
{
    bool IsRegistered { get; }
    HotkeyRegistrationResult Register(HotkeyDefinition hotkey, Action onPressed);
    void Unregister();
}

/// <summary>
/// Pure debounce/dedup logic for hotkey presses -- section 22's "key
/// debounce, repeated presses, key-down/key-up races, duplicate OS
/// hotkey events" requirement, factored out from any real OS event
/// source so it is fully testable with a fake clock, exactly like
/// VoiceSessionController's audio-free testability.
/// </summary>
public sealed class HotkeyDebouncer
{
    private readonly TimeSpan _window;
    private readonly Func<DateTime> _clock;
    private DateTime? _lastFired;

    public HotkeyDebouncer(TimeSpan window, Func<DateTime>? clock = null)
    {
        if (window < TimeSpan.Zero)
        {
            throw new ArgumentOutOfRangeException(nameof(window));
        }
        _window = window;
        _clock = clock ?? (() => DateTime.UtcNow);
    }

    /// <summary>Call once per raw OS "hotkey pressed" event. Returns
    /// true exactly when the press should actually be dispatched;
    /// false for a duplicate/bounced event within the debounce
    /// window, which the caller should silently drop.</summary>
    public bool ShouldFire()
    {
        var now = _clock();
        if (_lastFired.HasValue && now - _lastFired.Value < _window)
        {
            return false;
        }
        _lastFired = now;
        return true;
    }

    public void Reset()
    {
        _lastFired = null;
    }
}
