using System.Net.Http;
using System.Windows;
using AuraShell.Core;

namespace AuraShell;

/// <summary>
/// The single window this application ever shows (see App.xaml.cs) --
/// its content is entirely driven by InterfaceShellViewModel.Mode, never
/// a fixed dashboard:
///   Booting / AuthRequired / Authenticating / Locked / ErrorRecovery -> AuthenticationView
///   VoiceMode                                                        -> VoiceModeView
///   BackendAuthRequired / BackendAuthenticating                      -> BackendChallengeView
///   BackendMode                                                      -> BackendModeView
///
/// BackendModeView is where the previous Chat/Status/Approvals tabs and
/// the kill switch now live -- migrated, not deleted, per the
/// requirement that Backend Mode is where the old dashboard's
/// functionality resurfaces, never the owner's default startup screen.
/// </summary>
public partial class MainWindow : Window
{
    private readonly InterfaceShellViewModel _shell;
    private readonly AuraApiClient _apiClient;
    private Win32HotkeyManager? _hotkeyManager;
    private SystemSessionMonitor? _sessionMonitor;

    private readonly Views.AuthenticationView _authenticationView;
    private readonly Views.VoiceModeView _voiceModeView;
    private readonly Views.BackendChallengeView _backendChallengeView;
    private readonly Views.BackendModeView _backendModeView;

    public MainWindow(InterfaceShellViewModel shell, AuraApiClient apiClient)
    {
        InitializeComponent();
        _shell = shell;
        _apiClient = apiClient;

        _authenticationView = new Views.AuthenticationView { DataContext = shell };
        _voiceModeView = new Views.VoiceModeView { DataContext = shell.Voice };
        _backendChallengeView = new Views.BackendChallengeView { DataContext = shell };
        _backendModeView = new Views.BackendModeView { DataContext = shell };

        shell.Mode.ModeChanged += OnModeChanged;
        SourceInitialized += OnSourceInitialized;
        Closed += OnClosed;

        ApplyView(shell.Mode.Mode);
    }

    /// <summary>Called once by App.xaml.cs right after Show() -- runs the
    /// real startup sequence (bootstrap -> the real device-token check ->
    /// VoiceMode) with the window already visible and responsive, never a
    /// blocking splash the owner has to wait through in silence.</summary>
    public Task RunStartupSequenceAsync() => _shell.StartAsync();

    private void OnSourceInitialized(object? sender, EventArgs e)
    {
        _hotkeyManager = new Win32HotkeyManager(this);
        _sessionMonitor = new SystemSessionMonitor(this);
        _sessionMonitor.Locked += () => _ = _shell.OnSystemLockedAsync();
        _sessionMonitor.Unlocked += () => _ = _shell.OnSystemUnlockedAsync();
        _sessionMonitor.Start();

        _ = RegisterHotkeyAsync();
    }

    private async Task RegisterHotkeyAsync()
    {
        // The hotkey combination is centralized in aura_core's
        // /interface/config (see docs/VOICE_FIRST_SECURE_INTERFACE.md's
        // hotkey collision audit) -- this shell never hardcodes it.
        InterfaceConfig config;
        try
        {
            config = await _apiClient.GetInterfaceConfigAsync();
        }
        catch (HttpRequestException)
        {
            // aura_core unreachable at startup: the owner still gets a
            // working authentication/Voice Mode UI, just without the
            // hotkey registered until aura_core is reachable and this
            // shell is restarted. Fails closed (no hotkey), never
            // silently substitutes a hardcoded default.
            return;
        }

        var definition = HotkeyDefinition.Parse(config.BackendToggleHotkey);
        if (definition is null)
        {
            return;
        }

        // Registration failure (already in use by another application,
        // unsupported key name, etc.) is recorded on _hotkeyManager
        // itself (LastFailureDetail) for a future Diagnostics view to
        // surface -- Backend Mode simply becomes unreachable by hotkey
        // until it's fixed, never a crash and never a silent fallback to
        // a different key than the owner configured.
        _hotkeyManager!.Register(definition, OnHotkeyPressed);
    }

    private void OnHotkeyPressed() => _ = HandleHotkeyPressedAsync();

    private async Task HandleHotkeyPressedAsync()
    {
        try
        {
            await _shell.RequestBackendToggleAsync();
        }
        finally
        {
            _hotkeyManager?.ReleaseProcessingGate();
        }
    }

    private void OnModeChanged(InterfaceMode mode) => Dispatcher.Invoke(() => ApplyView(mode));

    private void ApplyView(InterfaceMode mode)
    {
        RootContent.Content = mode switch
        {
            InterfaceMode.VoiceMode => _voiceModeView,
            InterfaceMode.BackendAuthRequired => _backendChallengeView,
            InterfaceMode.BackendAuthenticating => _backendChallengeView,
            InterfaceMode.BackendMode => _backendModeView,
            _ => _authenticationView, // Booting, AuthRequired, Authenticating, Locked, ErrorRecovery
        };
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        _hotkeyManager?.Dispose();
        _sessionMonitor?.Dispose();
        _shell.Dispose();
    }
}
