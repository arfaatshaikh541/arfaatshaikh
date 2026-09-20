using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using AuraShell.Core;

namespace AuraShell.Views;

public partial class BackendChallengeView : UserControl
{
    public BackendChallengeView()
    {
        InitializeComponent();
        Loaded += (_, _) => PinBox.Focus();
        DataContextChanged += OnDataContextChanged;
    }

    private void OnDataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if (e.OldValue is InterfaceShellViewModel oldShell)
        {
            oldShell.PropertyChanged -= OnShellPropertyChanged;
        }
        if (e.NewValue is InterfaceShellViewModel newShell)
        {
            newShell.PropertyChanged += OnShellPropertyChanged;
            PinBox.Clear();
            Refresh(newShell);
        }
    }

    private void OnShellPropertyChanged(object? sender, PropertyChangedEventArgs e) =>
        Dispatcher.Invoke(() => Refresh((InterfaceShellViewModel)sender!));

    private void Refresh(InterfaceShellViewModel shell)
    {
        ErrorText.Text = shell.AuthErrorMessage ?? string.Empty;
        SubmitButton.IsEnabled = shell.Mode.Mode == InterfaceMode.BackendAuthRequired && PinBox.Password.Length > 0;

        // The PIN is cleared out of the view model as soon as it's
        // submitted (see SubmitBackendPinAsync) -- mirror that here so a
        // failed attempt never leaves the digits sitting visibly in the
        // box on the retry screen.
        if (shell.BackendPinInput.Length == 0 && PinBox.Password.Length > 0 && shell.Mode.Mode != InterfaceMode.BackendAuthenticating)
        {
            PinBox.Clear();
        }
    }

    private void OnPinChanged(object sender, RoutedEventArgs e)
    {
        if (DataContext is InterfaceShellViewModel shell)
        {
            shell.BackendPinInput = PinBox.Password;
            SubmitButton.IsEnabled = shell.Mode.Mode == InterfaceMode.BackendAuthRequired && PinBox.Password.Length > 0;
        }
    }

    private void OnSubmitClick(object sender, RoutedEventArgs e) =>
        (DataContext as InterfaceShellViewModel)?.SubmitBackendPinCommand.Execute(null);

    private void OnCancelClick(object sender, RoutedEventArgs e)
    {
        PinBox.Clear();
        (DataContext as InterfaceShellViewModel)?.CancelBackendAuthCommand.Execute(null);
    }
}
