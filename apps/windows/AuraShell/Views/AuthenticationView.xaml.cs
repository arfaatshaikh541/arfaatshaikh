using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using AuraShell.Core;

namespace AuraShell.Views;

public partial class AuthenticationView : UserControl
{
    public AuthenticationView()
    {
        InitializeComponent();
        DataContextChanged += OnDataContextChanged;
    }

    private void OnDataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if (e.OldValue is InterfaceShellViewModel oldShell)
        {
            oldShell.Mode.ModeChanged -= OnModeChanged;
            oldShell.PropertyChanged -= OnShellPropertyChanged;
        }
        if (e.NewValue is InterfaceShellViewModel newShell)
        {
            newShell.Mode.ModeChanged += OnModeChanged;
            newShell.PropertyChanged += OnShellPropertyChanged;
            Refresh(newShell);
        }
    }

    private void OnModeChanged(InterfaceMode _) => Dispatcher.Invoke(() => Refresh((InterfaceShellViewModel)DataContext));

    private void OnShellPropertyChanged(object? sender, PropertyChangedEventArgs e) =>
        Dispatcher.Invoke(() => Refresh((InterfaceShellViewModel)DataContext));

    private void Refresh(InterfaceShellViewModel shell)
    {
        switch (shell.Mode.Mode)
        {
            case InterfaceMode.Booting:
                StatusText.Text = "Starting AURA…";
                ActionButton.Visibility = Visibility.Collapsed;
                break;

            case InterfaceMode.Authenticating:
                StatusText.Text = "Verifying this device…";
                ActionButton.Visibility = Visibility.Collapsed;
                break;

            case InterfaceMode.Locked:
                StatusText.Text = "AURA is locked. Unlock Windows to continue.";
                ActionButton.Visibility = Visibility.Collapsed;
                break;

            case InterfaceMode.ErrorRecovery:
                StatusText.Text = "AURA hit an unexpected error and needs to restart its interface.";
                ActionButton.Content = "Recover";
                ActionButton.Command = shell.RecoverCommand;
                ActionButton.Visibility = Visibility.Visible;
                break;

            default: // AuthRequired
                StatusText.Text = shell.AuthErrorMessage ?? "Waiting to verify this device…";
                ActionButton.Content = "Retry";
                ActionButton.Command = shell.RetryAuthenticationCommand;
                ActionButton.Visibility = shell.AuthErrorMessage is null ? Visibility.Collapsed : Visibility.Visible;
                break;
        }
    }
}
