using AuraShell.Core;
using Xunit;

namespace AuraShell.Core.Tests;

public class InterfaceModeManagerTests
{
    [Fact]
    public void A_fresh_manager_always_starts_at_Booting()
    {
        var manager = new InterfaceModeManager();

        Assert.Equal(InterfaceMode.Booting, manager.Mode);
    }

    [Fact]
    public void The_full_startup_sequence_reaches_VoiceMode()
    {
        var manager = new InterfaceModeManager();

        manager.CompleteBootstrap();
        Assert.Equal(InterfaceMode.AuthRequired, manager.Mode);

        manager.BeginAuthentication();
        Assert.Equal(InterfaceMode.Authenticating, manager.Mode);

        manager.OnAuthenticationSucceeded();
        Assert.Equal(InterfaceMode.VoiceMode, manager.Mode);
    }

    [Fact]
    public void Failed_authentication_returns_to_AuthRequired_not_VoiceMode()
    {
        var manager = new InterfaceModeManager();
        manager.CompleteBootstrap();
        manager.BeginAuthentication();

        manager.OnAuthenticationFailed();

        Assert.Equal(InterfaceMode.AuthRequired, manager.Mode);
    }

    [Fact]
    public void The_backend_hotkey_from_VoiceMode_requires_authentication_first()
    {
        var manager = InVoiceMode();

        manager.RequestBackendToggle();

        Assert.Equal(InterfaceMode.BackendAuthRequired, manager.Mode);
        manager.BeginBackendAuthentication();
        Assert.Equal(InterfaceMode.BackendAuthenticating, manager.Mode);
        manager.OnBackendAuthenticationSucceeded();
        Assert.Equal(InterfaceMode.BackendMode, manager.Mode);
    }

    [Fact]
    public void The_same_hotkey_from_BackendMode_returns_to_VoiceMode_without_reauthentication()
    {
        var manager = InBackendMode();

        manager.RequestBackendToggle();

        Assert.Equal(InterfaceMode.VoiceMode, manager.Mode);
    }

    [Fact]
    public void The_hotkey_is_a_no_op_while_authenticating()
    {
        var manager = new InterfaceModeManager();
        manager.CompleteBootstrap();
        manager.BeginAuthentication();

        manager.RequestBackendToggle();

        Assert.Equal(InterfaceMode.Authenticating, manager.Mode); // unchanged, not an exception either
    }

    [Fact]
    public void The_hotkey_is_a_no_op_while_locked()
    {
        var manager = InVoiceMode();
        manager.Lock();

        manager.RequestBackendToggle();

        Assert.Equal(InterfaceMode.Locked, manager.Mode);
    }

    [Fact]
    public void Wrong_backend_credential_returns_to_BackendAuthRequired_for_a_retry()
    {
        var manager = InVoiceMode();
        manager.RequestBackendToggle();
        manager.BeginBackendAuthentication();

        manager.OnBackendAuthenticationFailed();

        Assert.Equal(InterfaceMode.BackendAuthRequired, manager.Mode);
    }

    [Fact]
    public void Cancelling_backend_authentication_returns_directly_to_VoiceMode()
    {
        var manager = InVoiceMode();
        manager.RequestBackendToggle();

        manager.CancelBackendAuthentication();

        Assert.Equal(InterfaceMode.VoiceMode, manager.Mode);
    }

    [Fact]
    public void Elevation_expiring_while_BackendMode_is_open_routes_back_through_authentication_not_straight_to_VoiceMode()
    {
        var manager = InBackendMode();

        manager.OnBackendElevationExpired();

        Assert.Equal(InterfaceMode.BackendAuthRequired, manager.Mode);
    }

    [Fact]
    public void Elevation_expiring_while_not_in_BackendMode_is_a_harmless_no_op()
    {
        var manager = InVoiceMode();

        manager.OnBackendElevationExpired();

        Assert.Equal(InterfaceMode.VoiceMode, manager.Mode);
    }

    [Fact]
    public void Lock_is_legal_from_VoiceMode_and_from_BackendMode()
    {
        var fromVoice = InVoiceMode();
        fromVoice.Lock();
        Assert.Equal(InterfaceMode.Locked, fromVoice.Mode);

        var fromBackend = InBackendMode();
        fromBackend.Lock();
        Assert.Equal(InterfaceMode.Locked, fromBackend.Mode);
    }

    [Fact]
    public void Unlocking_always_requires_fresh_authentication()
    {
        var manager = InVoiceMode();
        manager.Lock();

        manager.OnUnlockRequested();

        Assert.Equal(InterfaceMode.AuthRequired, manager.Mode);
    }

    [Fact]
    public void Error_recovery_is_legal_from_any_mode_and_always_routes_through_reauthentication()
    {
        var manager = InBackendMode();

        manager.EnterErrorRecovery();
        Assert.Equal(InterfaceMode.ErrorRecovery, manager.Mode);

        manager.OnRecovered();
        Assert.Equal(InterfaceMode.AuthRequired, manager.Mode); // never straight back to BackendMode
    }

    [Fact]
    public void An_invalid_transition_throws_rather_than_silently_changing_mode()
    {
        var manager = new InterfaceModeManager(); // Booting

        Assert.Throws<InvalidOperationException>(() => manager.OnAuthenticationSucceeded());
        Assert.Equal(InterfaceMode.Booting, manager.Mode);
    }

    [Fact]
    public void ModeChanged_fires_for_a_real_transition_but_not_for_a_repeated_hotkey_press_mid_flow()
    {
        var manager = InVoiceMode();
        var transitions = new List<InterfaceMode>();
        manager.ModeChanged += m => transitions.Add(m);

        manager.RequestBackendToggle(); // VoiceMode -> BackendAuthRequired: a real transition
        manager.RequestBackendToggle(); // pressed again while still BackendAuthRequired: a no-op, not VoiceMode or BackendMode

        Assert.Equal(new[] { InterfaceMode.BackendAuthRequired }, transitions);
    }

    private static InterfaceModeManager InVoiceMode()
    {
        var manager = new InterfaceModeManager();
        manager.CompleteBootstrap();
        manager.BeginAuthentication();
        manager.OnAuthenticationSucceeded();
        return manager;
    }

    private static InterfaceModeManager InBackendMode()
    {
        var manager = InVoiceMode();
        manager.RequestBackendToggle();
        manager.BeginBackendAuthentication();
        manager.OnBackendAuthenticationSucceeded();
        return manager;
    }
}
