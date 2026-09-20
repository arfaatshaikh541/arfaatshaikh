namespace AuraShell.Core;

/// <summary>
/// The application-level security/interface state machine (distinct
/// from, and layered above, AuraVoice.Core's VoiceSessionController,
/// which only models the conversational wake/listen/speak loop that
/// happens WHILE this manager is in VoiceMode). This is "AURA UI" in
/// the architectural-separation sense: it decides which surface is
/// visible and enforces the mode-transition rules, but it never itself
/// performs authentication or authorization -- every transition into an
/// authenticated or elevated state is driven by a real server response
/// (EnrollmentEngine.verify_token / BackendElevationService.authenticate
/// via AuraApiClient), never assumed client-side. A UI bug here can, at
/// worst, show the wrong screen; it cannot manufacture access, because
/// every protected server endpoint verifies independently regardless of
/// what this state machine believes.
/// </summary>
public enum InterfaceMode
{
    Booting,
    AuthRequired,
    Authenticating,
    VoiceMode,
    BackendAuthRequired,
    BackendAuthenticating,
    BackendMode,
    Locked,
    ErrorRecovery,
}

public sealed class InterfaceModeManager
{
    /// <summary>
    /// Always Booting -- this is what makes "a crash or restart while
    /// Backend Mode was open must never reopen Backend Mode" true
    /// structurally: there is no constructor path, no persisted field,
    /// no "last known mode" this class reads on startup. Every process
    /// start replays the full Booting -> AuthRequired -> ... sequence.
    /// </summary>
    public InterfaceMode Mode { get; private set; } = InterfaceMode.Booting;

    public event Action<InterfaceMode>? ModeChanged;

    /// <summary>Secure initialization (integrity check, required local
    /// services, encrypted identity load) has finished -- the owner may
    /// now be prompted to authenticate. Never skipped: there is no
    /// transition directly from Booting to anything else.</summary>
    public void CompleteBootstrap()
    {
        RequireMode(InterfaceMode.Booting);
        SetMode(InterfaceMode.AuthRequired);
    }

    public void BeginAuthentication()
    {
        RequireMode(InterfaceMode.AuthRequired);
        SetMode(InterfaceMode.Authenticating);
    }

    public void OnAuthenticationSucceeded()
    {
        RequireMode(InterfaceMode.Authenticating);
        SetMode(InterfaceMode.VoiceMode);
    }

    public void OnAuthenticationFailed()
    {
        RequireMode(InterfaceMode.Authenticating);
        SetMode(InterfaceMode.AuthRequired);
    }

    /// <summary>
    /// The single entry point for the backend hotkey, from any mode it
    /// is meaningful in -- callers never need to know which concrete
    /// transition applies; this method decides based on the current
    /// mode, exactly matching "the same shortcut toggles between Voice
    /// Mode and Backend Mode." Pressing it while neither mode is active
    /// (e.g. still authenticating, or locked) is a no-op: the hotkey
    /// only ever REQUESTS a transition, it never forces one out of an
    /// unrelated state.
    /// </summary>
    public void RequestBackendToggle()
    {
        switch (Mode)
        {
            case InterfaceMode.VoiceMode:
                SetMode(InterfaceMode.BackendAuthRequired);
                break;
            case InterfaceMode.BackendMode:
                SetMode(InterfaceMode.VoiceMode); // no re-auth required to LEAVE -- caller must still revoke elevation
                break;
            default:
                break; // ignored: debounced no-op, not an error (section 22)
        }
    }

    public void BeginBackendAuthentication()
    {
        RequireMode(InterfaceMode.BackendAuthRequired);
        SetMode(InterfaceMode.BackendAuthenticating);
    }

    public void OnBackendAuthenticationSucceeded()
    {
        RequireMode(InterfaceMode.BackendAuthenticating);
        SetMode(InterfaceMode.BackendMode);
    }

    /// <summary>Wrong PIN, wrong device, or rate-limited -- all return
    /// here rather than VoiceMode, so the owner can retry without
    /// losing the fact that they were mid-attempt. Explicit cancellation
    /// is a separate method.</summary>
    public void OnBackendAuthenticationFailed()
    {
        RequireMode(InterfaceMode.BackendAuthenticating);
        SetMode(InterfaceMode.BackendAuthRequired);
    }

    public void CancelBackendAuthentication()
    {
        if (Mode is InterfaceMode.BackendAuthRequired or InterfaceMode.BackendAuthenticating)
        {
            SetMode(InterfaceMode.VoiceMode);
        }
    }

    /// <summary>
    /// Section 14: elevation expiring while Backend Mode is still open
    /// must "immediately mask/lock sensitive content and require
    /// authentication again" -- distinct from the hotkey path, which
    /// leaves Backend Mode without any re-auth requirement. Expiry always
    /// routes back through BackendAuthRequired, never straight to
    /// VoiceMode, precisely because the owner did not deliberately choose
    /// to leave.
    /// </summary>
    public void OnBackendElevationExpired()
    {
        if (Mode == InterfaceMode.BackendMode)
        {
            SetMode(InterfaceMode.BackendAuthRequired);
        }
    }

    /// <summary>
    /// Idle timeout or an OS lock event -- legal from anywhere except
    /// Booting, matching VoiceSessionController's "the owner's stop
    /// request is always legal" precedent. Backend Mode is included
    /// deliberately (section 15: "Backend Mode must never remain
    /// accessible through an OS lock/unlock sequence without
    /// revalidation") -- locking from BackendMode does NOT, by itself,
    /// revoke the server-side elevation token; the caller (which does
    /// hold that token) is responsible for calling
    /// AuraApiClient.BackendDeauthenticateAsync alongside this.
    /// </summary>
    public void Lock()
    {
        if (Mode == InterfaceMode.Booting)
        {
            return;
        }
        SetMode(InterfaceMode.Locked);
    }

    public void OnUnlockRequested()
    {
        RequireMode(InterfaceMode.Locked);
        SetMode(InterfaceMode.AuthRequired);
    }

    /// <summary>
    /// Always legal -- an unrecoverable error must never leave the
    /// owner staring at a mode whose invariants no longer hold (e.g. a
    /// Backend Mode screen whose data loop has died). Recovery always
    /// routes back through full re-authentication, never straight to
    /// VoiceMode or BackendMode, for the same reason a crash does.
    /// </summary>
    public void EnterErrorRecovery()
    {
        SetMode(InterfaceMode.ErrorRecovery);
    }

    public void OnRecovered()
    {
        RequireMode(InterfaceMode.ErrorRecovery);
        SetMode(InterfaceMode.AuthRequired);
    }

    private void RequireMode(params InterfaceMode[] allowed)
    {
        if (Array.IndexOf(allowed, Mode) < 0)
        {
            throw new InvalidOperationException(
                $"operation is only valid from [{string.Join(", ", allowed)}], but current mode is {Mode}.");
        }
    }

    private void SetMode(InterfaceMode next)
    {
        if (Mode == next)
        {
            return;
        }
        Mode = next;
        ModeChanged?.Invoke(Mode);
    }
}
