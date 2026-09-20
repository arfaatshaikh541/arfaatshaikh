using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace AuraShell;

/// <summary>
/// Real Windows session-state notifications (section 16 of the
/// voice-first interface spec): lock/unlock/logoff via
/// WTSRegisterSessionNotification + WM_WTSSESSION_CHANGE, and
/// sleep/resume via WM_POWERBROADCAST. REQUIRES_WINDOWS_RUNTIME, the same
/// caveat as Win32HotkeyManager -- written against the documented Win32
/// APIs and against AuraShell.Core.InterfaceShellViewModel's already
/// -tested OnSystemLockedAsync/OnSystemUnlockedAsync, but never run
/// against a real Windows session or a real lock/sleep event.
///
/// Sleep is treated identically to a lock (both raise Locked): Backend
/// Mode's elevation must not survive a suspend/resume cycle any more than
/// it survives a lock/unlock cycle, and InterfaceShellViewModel's
/// OnSystemLockedAsync already performs the real revocation regardless of
/// which of these raised it.
/// </summary>
public sealed class SystemSessionMonitor : IDisposable
{
    private const int WM_WTSSESSION_CHANGE = 0x02B1;
    private const int WM_POWERBROADCAST = 0x0218;
    private const int WTS_SESSION_LOCK = 0x7;
    private const int WTS_SESSION_UNLOCK = 0x8;
    private const int WTS_SESSION_LOGOFF = 0x6;
    private const int WTS_CONSOLE_DISCONNECT = 0x2;
    private const int PBT_APMSUSPEND = 0x4;
    private const int PBT_APMRESUMESUSPEND = 0x7;
    private const int PBT_APMRESUMEAUTOMATIC = 0x12;
    private const uint NOTIFY_FOR_THIS_SESSION = 0;

    [DllImport("wtsapi32.dll", SetLastError = true)]
    private static extern bool WTSRegisterSessionNotification(IntPtr hWnd, uint dwFlags);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    private static extern bool WTSUnRegisterSessionNotification(IntPtr hWnd);

    private readonly Window _window;
    private HwndSource? _source;

    /// <summary>OS lock, logoff, console disconnect, or system suspend --
    /// every signal that means "the owner is no longer demonstrably
    /// present," all handled the same way by the caller.</summary>
    public event Action? Locked;

    public event Action? Unlocked;

    public bool IsRegistered { get; private set; }
    public string? LastFailureDetail { get; private set; }

    public SystemSessionMonitor(Window window)
    {
        _window = window;
    }

    public bool Start()
    {
        var helper = new WindowInteropHelper(_window);
        var hwnd = helper.Handle == IntPtr.Zero ? helper.EnsureHandle() : helper.Handle;
        var source = HwndSource.FromHwnd(hwnd);
        if (source is null)
        {
            LastFailureDetail = "no HwndSource for the shell window yet";
            return false;
        }

        if (!WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION))
        {
            LastFailureDetail = $"WTSRegisterSessionNotification failed with Win32 error {Marshal.GetLastWin32Error()}";
            return false;
        }

        _source = source;
        source.AddHook(WndProc);
        IsRegistered = true;
        LastFailureDetail = null;
        return true;
    }

    public void Stop()
    {
        if (!IsRegistered)
        {
            return;
        }

        var helper = new WindowInteropHelper(_window);
        if (helper.Handle != IntPtr.Zero)
        {
            WTSUnRegisterSessionNotification(helper.Handle);
        }
        _source?.RemoveHook(WndProc);
        _source = null;
        IsRegistered = false;
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == WM_WTSSESSION_CHANGE)
        {
            switch (wParam.ToInt32())
            {
                case WTS_SESSION_LOCK:
                case WTS_SESSION_LOGOFF:
                case WTS_CONSOLE_DISCONNECT:
                    Locked?.Invoke();
                    break;
                case WTS_SESSION_UNLOCK:
                    Unlocked?.Invoke();
                    break;
            }
        }
        else if (msg == WM_POWERBROADCAST)
        {
            switch (wParam.ToInt32())
            {
                case PBT_APMSUSPEND:
                    Locked?.Invoke();
                    break;
                case PBT_APMRESUMESUSPEND:
                case PBT_APMRESUMEAUTOMATIC:
                    Unlocked?.Invoke();
                    break;
            }
        }
        return IntPtr.Zero;
    }

    public void Dispose() => Stop();
}
