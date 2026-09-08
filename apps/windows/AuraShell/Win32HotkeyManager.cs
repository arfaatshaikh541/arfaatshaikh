using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;

namespace AuraShell;

/// <summary>
/// The real Win32 implementation of AuraShell.Core.IHotkeyManager --
/// RegisterHotKey / UnregisterHotKey plus a WM_HOTKEY hook on the shell's
/// own window handle. REQUIRES_WINDOWS_RUNTIME: this file lives in a
/// net8.0-windows/UseWPF project that cannot be built or run outside
/// Windows (see this folder's README.md) -- nothing here has been
/// exercised against a real window or a real RegisterHotKey call. It is
/// written to use exactly AuraShell.Core's already-tested
/// HotkeyDefinition/HotkeyRegistrationResult/HotkeyDebouncer contract, so
/// the parts that CAN be verified without Windows (parsing, debounce
/// timing, registration-result shape) already are -- see
/// HotkeyManagerTests.cs in AuraShell.Core.Tests.
/// </summary>
public sealed class Win32HotkeyManager : Core.IHotkeyManager
{
    private const int WM_HOTKEY = 0x0312;
    private const uint MOD_ALT = 0x0001;
    private const uint MOD_CONTROL = 0x0002;
    private const uint MOD_SHIFT = 0x0004;
    private const uint MOD_WIN = 0x0008;
    private const int ERROR_HOTKEY_ALREADY_REGISTERED = 1409;

    // This shell only ever registers one hotkey (the backend toggle) at a
    // time, so a single fixed id is sufficient -- no pool needed.
    private const int HotkeyId = 0xA000;

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    private readonly Window _window;
    private readonly Core.HotkeyDebouncer _debouncer;
    private HwndSource? _source;
    private Action? _onPressed;
    private bool _isProcessing;

    public bool IsRegistered { get; private set; }

    /// <summary>Set whenever Register/Unregister did not succeed, for a
    /// future Backend Mode Diagnostics view to surface honestly rather
    /// than silently leaving the hotkey non-functional with no
    /// explanation anywhere.</summary>
    public string? LastFailureDetail { get; private set; }

    public Win32HotkeyManager(Window window, TimeSpan? debounceWindow = null)
    {
        _window = window;
        _debouncer = new Core.HotkeyDebouncer(debounceWindow ?? TimeSpan.FromMilliseconds(400));
    }

    public Core.HotkeyRegistrationResult Register(Core.HotkeyDefinition hotkey, Action onPressed)
    {
        Unregister(); // clean re-registration -- never two live registrations at once

        var helper = new WindowInteropHelper(_window);
        var hwnd = helper.Handle == IntPtr.Zero ? helper.EnsureHandle() : helper.Handle;
        var source = HwndSource.FromHwnd(hwnd);
        if (source is null)
        {
            LastFailureDetail = "no HwndSource for the shell window yet";
            return new Core.HotkeyRegistrationResult(Core.HotkeyRegistrationStatus.Failed, LastFailureDetail);
        }

        if (!Enum.TryParse<Key>(hotkey.Key, ignoreCase: true, out var key) || key == Key.None)
        {
            LastFailureDetail = $"'{hotkey.Key}' is not a recognized key name";
            return new Core.HotkeyRegistrationResult(Core.HotkeyRegistrationStatus.Unsupported, LastFailureDetail);
        }

        var vk = (uint)KeyInterop.VirtualKeyFromKey(key);
        uint modifiers = 0;
        if (hotkey.Ctrl) modifiers |= MOD_CONTROL;
        if (hotkey.Alt) modifiers |= MOD_ALT;
        if (hotkey.Shift) modifiers |= MOD_SHIFT;
        if (hotkey.Win) modifiers |= MOD_WIN;

        if (!RegisterHotKey(hwnd, HotkeyId, modifiers, vk))
        {
            var error = Marshal.GetLastWin32Error();
            LastFailureDetail = $"RegisterHotKey failed with Win32 error {error}";
            var status = error == ERROR_HOTKEY_ALREADY_REGISTERED
                ? Core.HotkeyRegistrationStatus.AlreadyInUse
                : Core.HotkeyRegistrationStatus.Failed;
            return new Core.HotkeyRegistrationResult(status, LastFailureDetail);
        }

        _source = source;
        _onPressed = onPressed;
        _debouncer.Reset();
        source.AddHook(WndProc);
        IsRegistered = true;
        LastFailureDetail = null;
        return new Core.HotkeyRegistrationResult(Core.HotkeyRegistrationStatus.Registered);
    }

    public void Unregister()
    {
        if (!IsRegistered)
        {
            return;
        }

        var helper = new WindowInteropHelper(_window);
        if (helper.Handle != IntPtr.Zero)
        {
            UnregisterHotKey(helper.Handle, HotkeyId);
        }
        _source?.RemoveHook(WndProc);
        _source = null;
        _onPressed = null;
        IsRegistered = false;
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg != WM_HOTKEY || wParam.ToInt32() != HotkeyId)
        {
            return IntPtr.Zero;
        }

        handled = true;

        // Debounce first (repeated presses, key-down/key-up races,
        // duplicate OS hotkey events), then refuse re-entrancy while a
        // prior press's async mode-transition work is still in flight --
        // a second WM_HOTKEY arriving mid-transition is dropped, not
        // queued, since InterfaceModeManager's transitions are not
        // designed to be entered concurrently.
        if (!_debouncer.ShouldFire() || _isProcessing)
        {
            return IntPtr.Zero;
        }

        _isProcessing = true;
        _onPressed?.Invoke();
        return IntPtr.Zero;
    }

    /// <summary>
    /// Called once the async work _onPressed kicked off has actually
    /// finished, so the next real hotkey press is accepted again.
    /// Deliberately explicit rather than automatic: onPressed is a plain
    /// synchronous Action (matching IHotkeyManager exactly, so this class
    /// stays swappable with any future non-Win32 implementation), not a
    /// Func&lt;Task&gt;, so this manager has no way to await it itself --
    /// see MainWindow.xaml.cs's HandleHotkeyPressedAsync for the caller
    /// that awaits the real work and then calls this in a finally block.
    /// </summary>
    public void ReleaseProcessingGate() => _isProcessing = false;

    public void Dispose() => Unregister();
}
