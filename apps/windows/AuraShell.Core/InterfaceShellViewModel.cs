using System.Collections.ObjectModel;
using System.Windows.Input;

namespace AuraShell.Core;

/// <summary>
/// Composition root for the real voice-first shell (App.xaml.cs's single
/// entry point, replacing the old MainWindow-first launch): owns
/// InterfaceModeManager, the Voice Mode and Backend Mode view models, and
/// every side effect a mode transition requires that InterfaceModeManager
/// itself deliberately does not perform (it is pure state, with no
/// network access at all — see its own docs). This class is what makes
/// "press the hotkey" actually revoke elevation, stop/restart the voice
/// state subscription, and drive the real /backend/authenticate call —
/// while InterfaceModeManager still independently governs which
/// transitions are legal in the first place.
///
/// Every security-relevant fact this class relies on is re-verified by
/// aura_core on the next real request regardless of what this class
/// believes (see require_device_token / require_backend_elevation in
/// api/app.py) — a bug here can show the wrong screen, but it cannot by
/// itself grant access to anything.
/// </summary>
public sealed class InterfaceShellViewModel : ObservableObject, IDisposable
{
    private readonly AuraApiClient _client;
    private readonly TimeSpan _elevationPollInterval;
    private string? _elevationToken;
    private CancellationTokenSource? _elevationMonitorCts;

    private string _backendPinInput = string.Empty;
    private string? _authErrorMessage;
    private TimeSpan? _elevationRemaining;
    private string? _ownerName;
    private BackendDiagnostics? _diagnostics;

    public InterfaceModeManager Mode { get; }
    public VoiceModeViewModel Voice { get; }
    public MainViewModel Backend { get; }

    /// <summary>Real system state from /backend/diagnostics (audit chain
    /// validity, recent Security Guardian events, capability status) —
    /// null until SubmitBackendPinAsync succeeds at least once, never a
    /// fabricated placeholder. See Models.cs's BackendDiagnostics for why
    /// its nested fields stay raw JSON rather than re-typed here.</summary>
    public BackendDiagnostics? Diagnostics
    {
        get => _diagnostics;
        private set => SetProperty(ref _diagnostics, value);
    }

    /// <summary>The real hash-chained audit trail (/backend/audit), owner
    /// facing per section 32's "Audit Trail" Backend Mode view — nothing
    /// here is synthesized.</summary>
    public ObservableCollection<AuditEntryInfo> AuditEntries { get; } = new();

    public ICommand RefreshDiagnosticsCommand { get; }
    public ICommand RefreshAuditCommand { get; }

    /// <summary>Real multi-device trust (identity/enrollment.py's
    /// DeviceTrust) — every row here is a real, currently-enrolled or
    /// revoked device, never fabricated demo data.</summary>
    public ObservableCollection<DeviceInfo> Devices { get; } = new();

    private DeviceInfo? _selectedDevice;
    public DeviceInfo? SelectedDevice
    {
        get => _selectedDevice;
        set
        {
            if (SetProperty(ref _selectedDevice, value))
            {
                (RevokeSelectedDeviceCommand as RelayCommand)?.RaiseCanExecuteChanged();
                (RenameSelectedDeviceCommand as RelayCommand)?.RaiseCanExecuteChanged();
            }
        }
    }

    private string _renameInput = string.Empty;
    public string RenameInput
    {
        get => _renameInput;
        set
        {
            if (SetProperty(ref _renameInput, value))
            {
                (RenameSelectedDeviceCommand as RelayCommand)?.RaiseCanExecuteChanged();
            }
        }
    }

    /// <summary>The active "Add Device" pairing code (section 15/16) —
    /// null except for the brief window between StartDevicePairingAsync
    /// succeeding and the code expiring or being claimed. Never persisted
    /// -- a fresh page load or mode re-entry shows nothing until the
    /// owner starts a new session, matching the server's own
    /// in-memory-only pairing sessions (identity/pairing.py).</summary>
    public string? PairingCode
    {
        get => _pairingCode;
        private set => SetProperty(ref _pairingCode, value);
    }
    private string? _pairingCode;

    /// <summary>Base64-encoded PNG of a QR code encoding the same
    /// pairing code plus this server's address (see
    /// aura_core.identity.qr) -- a convenience the owner can scan
    /// instead of typing PairingCode by hand. Never a separate
    /// credential: scanning it still redeems the exact same code above.
    /// Null under the same conditions as PairingCode.</summary>
    public string? PairingQrPngBase64
    {
        get => _pairingQrPngBase64;
        private set => SetProperty(ref _pairingQrPngBase64, value);
    }
    private string? _pairingQrPngBase64;

    public DateTime? PairingExpiresAtUtc
    {
        get => _pairingExpiresAtUtc;
        private set => SetProperty(ref _pairingExpiresAtUtc, value);
    }
    private DateTime? _pairingExpiresAtUtc;

    public string? DeviceOperationError
    {
        get => _deviceOperationError;
        private set => SetProperty(ref _deviceOperationError, value);
    }
    private string? _deviceOperationError;

    public ICommand RefreshDevicesCommand { get; }
    public ICommand StartDevicePairingCommand { get; }
    public ICommand RevokeSelectedDeviceCommand { get; }
    public ICommand RenameSelectedDeviceCommand { get; }

    public string? OwnerName
    {
        get => _ownerName;
        private set => SetProperty(ref _ownerName, value);
    }

    public string BackendPinInput
    {
        get => _backendPinInput;
        set
        {
            if (SetProperty(ref _backendPinInput, value))
            {
                (SubmitBackendPinCommand as RelayCommand)?.RaiseCanExecuteChanged();
            }
        }
    }

    public string? AuthErrorMessage
    {
        get => _authErrorMessage;
        private set => SetProperty(ref _authErrorMessage, value);
    }

    /// <summary>UX-only countdown for the Backend Mode chrome (e.g. "12:47
    /// remaining"). Never the thing that actually ends the session — see
    /// MonitorElevationAsync's docs.</summary>
    public TimeSpan? ElevationRemaining
    {
        get => _elevationRemaining;
        private set => SetProperty(ref _elevationRemaining, value);
    }

    public ICommand SubmitBackendPinCommand { get; }
    public ICommand CancelBackendAuthCommand { get; }
    public ICommand RetryAuthenticationCommand { get; }
    public ICommand RecoverCommand { get; }

    public InterfaceShellViewModel(AuraApiClient client, TimeSpan? elevationPollInterval = null)
    {
        _client = client;
        _elevationPollInterval = elevationPollInterval ?? TimeSpan.FromSeconds(5);
        Mode = new InterfaceModeManager();
        Voice = new VoiceModeViewModel(client);
        Backend = new MainViewModel(client);
        SubmitBackendPinCommand = new RelayCommand(SubmitBackendPinAsync, () => !string.IsNullOrWhiteSpace(BackendPinInput));
        CancelBackendAuthCommand = new RelayCommand(CancelBackendAuthAsync);
        RefreshDiagnosticsCommand = new RelayCommand(RefreshDiagnosticsAsync);
        RefreshAuditCommand = new RelayCommand(RefreshAuditAsync);
        RefreshDevicesCommand = new RelayCommand(RefreshDevicesAsync);
        StartDevicePairingCommand = new RelayCommand(StartDevicePairingAsync);
        RevokeSelectedDeviceCommand = new RelayCommand(RevokeSelectedDeviceAsync, () => SelectedDevice is not null);
        RenameSelectedDeviceCommand = new RelayCommand(
            RenameSelectedDeviceAsync, () => SelectedDevice is not null && !string.IsNullOrWhiteSpace(RenameInput));
        // AuthenticateAsync requires Mode == AuthRequired (see
        // InterfaceModeManager.BeginAuthentication) -- that's exactly the
        // mode a failed attempt returns to, so this is a legal "Retry"
        // action anywhere the authentication screen is actually showing.
        RetryAuthenticationCommand = new RelayCommand(AuthenticateAsync);
        RecoverCommand = new RelayCommand(RecoverAsync);
    }

    /// <summary>
    /// The only way out of ErrorRecovery (section: "an unrecoverable
    /// error must never leave the owner staring at a broken screen
    /// forever"). Always re-enters through the same real device-token
    /// check every other path into VoiceMode uses -- there is no
    /// shortcut back into BackendMode from here.
    /// </summary>
    private Task RecoverAsync()
    {
        Mode.OnRecovered();
        return AuthenticateAsync();
    }

    /// <summary>No-op (not an error) without an active elevation — every
    /// Backend Mode view that calls this only exists while BackendMode is
    /// current, but defends itself anyway rather than trusting caller
    /// discipline.</summary>
    public async Task RefreshDiagnosticsAsync()
    {
        if (_elevationToken is null)
        {
            return;
        }
        Diagnostics = await _client.GetBackendDiagnosticsAsync(_elevationToken);
    }

    public async Task RefreshAuditAsync()
    {
        if (_elevationToken is null)
        {
            return;
        }
        var entries = await _client.GetBackendAuditAsync(_elevationToken);
        AuditEntries.Clear();
        foreach (var entry in entries)
        {
            AuditEntries.Add(entry);
        }
    }

    public async Task RefreshDevicesAsync()
    {
        if (_elevationToken is null)
        {
            return;
        }
        var devices = await _client.GetDevicesAsync(_elevationToken);
        Devices.Clear();
        foreach (var device in devices)
        {
            Devices.Add(device);
        }
    }

    /// <summary>
    /// The root side of the "Add Device" flow (section 15/16): mints a
    /// real, short-lived pairing code the owner shows (as text or a QR
    /// code) to the new device. Only reachable from Backend Mode, which
    /// already required a fresh PIN challenge to enter -- there is no
    /// separate, weaker gate just for this action.
    /// </summary>
    public async Task StartDevicePairingAsync()
    {
        if (_elevationToken is null)
        {
            return;
        }
        try
        {
            var session = await _client.StartDevicePairingAsync(_elevationToken);
            PairingCode = session.Code;
            PairingQrPngBase64 = session.QrPngBase64;
            PairingExpiresAtUtc = DateTimeOffset.Parse(session.ExpiresAt).UtcDateTime;
            DeviceOperationError = null;
        }
        catch (HttpRequestException)
        {
            DeviceOperationError = "Could not start a pairing session.";
        }
    }

    private async Task RevokeSelectedDeviceAsync()
    {
        if (_elevationToken is null || SelectedDevice is null)
        {
            return;
        }
        await _client.RevokeDeviceAsync(SelectedDevice.Id, _elevationToken);
        SelectedDevice = null;
        await RefreshDevicesAsync();
    }

    private async Task RenameSelectedDeviceAsync()
    {
        if (_elevationToken is null || SelectedDevice is null || string.IsNullOrWhiteSpace(RenameInput))
        {
            return;
        }
        await _client.RenameDeviceAsync(SelectedDevice.Id, RenameInput, _elevationToken);
        RenameInput = string.Empty;
        await RefreshDevicesAsync();
    }

    /// <summary>
    /// The application's one and only startup path (section 3 / 4):
    /// Booting -> AuthRequired -> the real startup authentication check
    /// -> VoiceMode. There is no other route into this object's modes
    /// that skips this — a crash or restart always re-enters here, never
    /// resuming a persisted "last mode," because InterfaceModeManager
    /// itself always constructs into Booting.
    /// </summary>
    public Task StartAsync()
    {
        Mode.CompleteBootstrap();
        return AuthenticateAsync();
    }

    /// <summary>
    /// An optional, additional interactive owner-presence factor run
    /// BEFORE the device-token check below -- set by the WPF host
    /// (App.xaml.cs/MainWindow) to a real Windows credential prompt
    /// (see AuraShell's WindowsOwnerPresenceVerifier), never set here
    /// since this class must stay testable without any Windows API.
    /// Null (the default, used by every existing test) means "no
    /// additional local factor configured" -- AuthenticateAsync then
    /// falls back to the device-token check alone, exactly as before.
    /// A thrown exception from this delegate is treated as "not
    /// verified," never propagated -- a broken presence check must fail
    /// closed, the same discipline every credential check in this
    /// codebase already follows.
    /// </summary>
    public Func<Task<bool>>? OwnerPresenceCheck { get; set; }

    /// <summary>
    /// The real production startup authentication check. Two factors
    /// when OwnerPresenceCheck is configured: (1) a real interactive
    /// owner-presence verification the WPF host performs locally (a
    /// Windows credential prompt, not merely "a window is focused"),
    /// and (2) the existing device-trust check (identity/whoami) that
    /// runs regardless. Neither factor is Windows Hello / biometric --
    /// that hardware-backed factor remains unbuilt, named honestly in
    /// docs/VOICE_FIRST_SECURE_INTERFACE.md. Retryable: on failure, Mode
    /// returns to AuthRequired, from which this may be called again
    /// (e.g. a "Retry" button, or after `aura enroll` was run on this
    /// machine while the screen was showing).
    /// </summary>
    public async Task AuthenticateAsync()
    {
        Mode.BeginAuthentication();

        if (OwnerPresenceCheck is not null)
        {
            bool present;
            try
            {
                present = await OwnerPresenceCheck();
            }
            catch (Exception)
            {
                present = false;
            }

            if (!present)
            {
                AuthErrorMessage = "Owner presence could not be verified.";
                Mode.OnAuthenticationFailed();
                return;
            }
        }

        try
        {
            var whoami = await _client.GetWhoAmIAsync();
            if (!whoami.Enrolled)
            {
                AuthErrorMessage = "No owner is enrolled on this installation yet. Run \"aura enroll\" first.";
                Mode.OnAuthenticationFailed();
                return;
            }

            OwnerName = whoami.OwnerName;
            AuthErrorMessage = null;
            Mode.OnAuthenticationSucceeded();
            Voice.StartObserving();
        }
        catch (HttpRequestException)
        {
            AuthErrorMessage = "This device is not recognized by aura_core. Re-run \"aura enroll\" on this machine.";
            Mode.OnAuthenticationFailed();
        }
    }

    /// <summary>
    /// The hotkey's single entry point — Win32HotkeyManager's callback
    /// calls exactly this, from either mode, on every debounced press.
    /// Which concrete transition applies is InterfaceModeManager's
    /// decision; this method only carries out the network side effects
    /// that decision demands (revoking elevation on the way out, and
    /// starting/stopping the voice-state subscription so Backend Mode
    /// and Voice Mode never both hold it at once).
    /// </summary>
    public async Task RequestBackendToggleAsync()
    {
        var wasBackendMode = Mode.Mode == InterfaceMode.BackendMode;
        Mode.RequestBackendToggle();

        if (wasBackendMode && Mode.Mode == InterfaceMode.VoiceMode)
        {
            await LeaveBackendModeAsync();
        }
        else if (Mode.Mode == InterfaceMode.BackendAuthRequired)
        {
            Voice.StopObserving();
            AuthErrorMessage = null;
            BackendPinInput = string.Empty;
        }
    }

    public async Task SubmitBackendPinAsync()
    {
        var pin = BackendPinInput;
        BackendPinInput = string.Empty;
        Mode.BeginBackendAuthentication();
        try
        {
            var result = await _client.BackendAuthenticateAsync(pin);
            _elevationToken = result.ElevationToken;
            AuthErrorMessage = null;
            Mode.OnBackendAuthenticationSucceeded();
            StartElevationMonitor(TimeSpan.FromSeconds(result.ExpiresInSeconds));
        }
        catch (HttpRequestException)
        {
            // Never distinguishes "wrong PIN" from "untrusted device" from
            // "rate limited" -- matching the server's own refusal to say
            // (identity/elevation.py), so a voice/UI attacker gains no
            // information about which factor to try next.
            AuthErrorMessage = "Backend authentication failed.";
            Mode.OnBackendAuthenticationFailed();
            return;
        }

        // Deliberately outside the authentication try/catch above: a
        // genuinely successful PIN authentication must never be rolled
        // back into BackendAuthRequired just because the diagnostics or
        // audit fetch that follows it happened to fail (aura_core
        // briefly unreachable, etc.) -- Backend Mode still opens, its
        // Diagnostics/AuditEntries panels simply stay empty until the
        // owner refreshes them, same as any other real, honest failure
        // this codebase reports rather than papering over.
        try
        {
            await Backend.InitializeAsync();
            await RefreshDiagnosticsAsync();
            await RefreshAuditAsync();
            await RefreshDevicesAsync();
        }
        catch (HttpRequestException)
        {
        }
    }

    private Task CancelBackendAuthAsync()
    {
        Mode.CancelBackendAuthentication();
        BackendPinInput = string.Empty;
        AuthErrorMessage = null;
        Voice.StartObserving();
        return Task.CompletedTask;
    }

    private async Task LeaveBackendModeAsync()
    {
        StopElevationMonitor();
        var token = _elevationToken;
        _elevationToken = null;
        ElevationRemaining = null;
        // Clear sensitive state (section 15) -- Backend Mode leaving must
        // wipe what it showed, not merely hide the view that showed it.
        Diagnostics = null;
        AuditEntries.Clear();
        Devices.Clear();
        SelectedDevice = null;
        RenameInput = string.Empty;
        PairingCode = null;
        PairingQrPngBase64 = null;
        PairingExpiresAtUtc = null;
        if (token is not null)
        {
            try
            {
                await _client.BackendDeauthenticateAsync(token);
            }
            catch (HttpRequestException)
            {
                // Best-effort: the server-side session still expires on
                // its own TTL even if this particular revoke call failed
                // to land (e.g. aura_core briefly unreachable).
            }
        }
        Voice.StartObserving();
    }

    /// <summary>
    /// A real OS lock (SystemSessionMonitor, WPF-only, calls this from a
    /// genuine WTS session-change notification) is legal from any active
    /// mode and must never leave Backend Mode's elevation valid across
    /// it — this revokes it exactly the same way the hotkey's "leave
    /// Backend Mode" path does, then locks.
    /// </summary>
    public async Task OnSystemLockedAsync()
    {
        if (Mode.Mode == InterfaceMode.BackendMode)
        {
            await LeaveBackendModeAsync();
        }
        else
        {
            Voice.StopObserving();
        }
        Mode.Lock();
    }

    /// <summary>Unlocking never restores Backend Mode or any prior
    /// elevation by itself -- it always re-enters through the same
    /// AuthenticateAsync() the initial launch uses.</summary>
    public Task OnSystemUnlockedAsync()
    {
        Mode.OnUnlockRequested();
        return AuthenticateAsync();
    }

    private void StartElevationMonitor(TimeSpan initialTtl)
    {
        StopElevationMonitor();
        ElevationRemaining = initialTtl;
        var cts = new CancellationTokenSource();
        _elevationMonitorCts = cts;
        _ = MonitorElevationAsync(cts.Token);
    }

    private void StopElevationMonitor()
    {
        _elevationMonitorCts?.Cancel();
        _elevationMonitorCts?.Dispose();
        _elevationMonitorCts = null;
    }

    /// <summary>
    /// A convenience UX timer only -- NOT the security boundary. The
    /// real enforcement is server-side: every /backend/* call
    /// independently re-checks the elevation token
    /// (BackendElevationService.verify), so even if this loop never ran
    /// at all, a request made with an expired token would still be
    /// rejected. What this loop buys is proactively returning the owner
    /// to BackendAuthRequired *before* they notice a request fail, even
    /// with the UI otherwise idle — but the guarantee that expired
    /// elevation can never be used comes from the server check, which
    /// runs whether or not this loop is alive.
    /// </summary>
    private async Task MonitorElevationAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                await Task.Delay(_elevationPollInterval, ct);
            }
            catch (OperationCanceledException)
            {
                return;
            }

            var token = _elevationToken;
            if (token is null)
            {
                return;
            }

            BackendSessionStatus? status;
            try
            {
                status = await _client.GetBackendSessionAsync(token, ct);
            }
            catch (OperationCanceledException)
            {
                return;
            }
            catch (HttpRequestException)
            {
                continue;
            }

            if (status is null || !status.Active)
            {
                _elevationToken = null;
                ElevationRemaining = null;
                Diagnostics = null;
                AuditEntries.Clear();
                Devices.Clear();
                SelectedDevice = null;
                RenameInput = string.Empty;
                PairingCode = null;
                PairingQrPngBase64 = null;
                PairingExpiresAtUtc = null;
                Mode.OnBackendElevationExpired();
                Voice.StartObserving();
                return;
            }

            ElevationRemaining = TimeSpan.FromSeconds(status.SecondsRemaining);
        }
    }

    public void Dispose()
    {
        StopElevationMonitor();
        Voice.Dispose();
    }
}
