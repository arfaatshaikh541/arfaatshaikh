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
    /// The real substitute this build has for a production startup
    /// authentication screen: no Windows Hello or other hardware-backed
    /// factor is wired up, so "is the owner present" is answered the
    /// same way every other trust decision in this codebase already is —
    /// a valid device token (identity/whoami) — rather than inventing a
    /// separate, weaker check just for this screen. Retryable: on
    /// failure, Mode returns to AuthRequired, from which this may be
    /// called again (e.g. a "Retry" button, or after `aura enroll` was
    /// run on this machine while the screen was showing).
    /// </summary>
    public async Task AuthenticateAsync()
    {
        Mode.BeginAuthentication();
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
