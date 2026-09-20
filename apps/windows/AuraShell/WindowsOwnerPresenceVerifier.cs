using System.Runtime.InteropServices;

namespace AuraShell;

/// <summary>
/// A real, interactive owner-presence factor for the startup screen,
/// beyond mere device trust (see docs/VOICE_FIRST_SECURE_INTERFACE.md's
/// "the real substitute for Windows Hello"): verifies the CURRENT
/// Windows account's own password via the standard LogonUser Win32 API
/// -- the same primitive Windows itself uses to validate credentials
/// during an interactive logon or unlock. This is not Windows Hello (no
/// biometric or hardware-backed factor is used), but it is a genuine
/// "does the person at the keyboard know this account's password right
/// now" check, using a single long-stable, extensively documented Win32
/// API rather than a WinRT/UWP projection this sandbox has no way to
/// verify the exact binding shape of.
///
/// REQUIRES_WINDOWS_RUNTIME: never compiled or exercised against a real
/// Windows account in this sandbox (no Windows machine exists here at
/// all, let alone one with a real account to call LogonUser against).
/// Wired into InterfaceShellViewModel.OwnerPresenceCheck by MainWindow
/// (see OwnerPresenceDialog.xaml.cs), which stays entirely optional --
/// a null OwnerPresenceCheck (the default, and what every Linux-run
/// AuraShell.Core.Tests test exercises) leaves prior behavior unchanged.
/// </summary>
public static class WindowsOwnerPresenceVerifier
{
    private const int LOGON32_LOGON_INTERACTIVE = 2;
    private const int LOGON32_PROVIDER_DEFAULT = 0;

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool LogonUser(
        string lpszUsername,
        string? lpszDomain,
        string lpszPassword,
        int dwLogonType,
        int dwLogonProvider,
        out IntPtr phToken);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    /// <summary>The account this process is running as -- shown to the
    /// owner in the prompt so it is unambiguous which password is being
    /// asked for, never assumed silently.</summary>
    public static string CurrentAccountName => Environment.UserName;

    /// <summary>
    /// Verifies <paramref name="password"/> against the currently
    /// logged-in Windows account. Never throws for a wrong password --
    /// returns false, exactly like every other credential check in this
    /// codebase (BackendElevationService.authenticate,
    /// EnrollmentEngine.verify_owner_pin) that never distinguishes "wrong
    /// secret" from any other failure via an exception. The handle
    /// LogonUser returns on success is closed immediately -- this call
    /// only ever proves possession of the password, it never needs to
    /// impersonate or hold the resulting token open.
    /// </summary>
    public static bool Verify(string password)
    {
        if (string.IsNullOrEmpty(password))
        {
            return false;
        }

        bool success;
        try
        {
            success = LogonUser(
                Environment.UserName,
                Environment.UserDomainName,
                password,
                LOGON32_LOGON_INTERACTIVE,
                LOGON32_PROVIDER_DEFAULT,
                out var token);
            if (success)
            {
                CloseHandle(token);
            }
        }
        catch (Exception)
        {
            // Fail closed on anything unexpected (e.g. the account is a
            // domain account whose domain controller is unreachable) --
            // never treat an inconclusive check as a pass.
            return false;
        }

        return success;
    }
}
