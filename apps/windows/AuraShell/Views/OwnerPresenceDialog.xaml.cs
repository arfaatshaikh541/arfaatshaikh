using System.Windows;

namespace AuraShell.Views;

public partial class OwnerPresenceDialog : Window
{
    private bool _verified;

    public OwnerPresenceDialog()
    {
        InitializeComponent();
        AccountText.Text = $"Windows account: {WindowsOwnerPresenceVerifier.CurrentAccountName}";
        Loaded += (_, _) => PasswordBox.Focus();
    }

    /// <summary>
    /// Shows the dialog modally and returns whether the entered password
    /// verified against the current Windows account -- false both for a
    /// wrong password and for an explicit Cancel, matching every other
    /// credential check in this codebase's refusal to distinguish "wrong
    /// secret" from "declined" via a different outcome. Must run on the
    /// UI thread (WPF's ShowDialog requirement) --
    /// InterfaceShellViewModel.AuthenticateAsync's continuation runs
    /// there by construction (WPF's own SynchronizationContext), so no
    /// explicit Dispatcher hop is needed by the caller.
    /// </summary>
    public static bool ShowAndVerify(Window owner)
    {
        var dialog = new OwnerPresenceDialog { Owner = owner };
        dialog.ShowDialog();
        return dialog._verified;
    }

    private void OnOkClick(object sender, RoutedEventArgs e)
    {
        if (WindowsOwnerPresenceVerifier.Verify(PasswordBox.Password))
        {
            _verified = true;
            DialogResult = true;
        }
        else
        {
            ErrorText.Text = "That password didn't verify. Try again.";
            PasswordBox.Clear();
            PasswordBox.Focus();
        }
    }

    private void OnCancelClick(object sender, RoutedEventArgs e)
    {
        _verified = false;
        DialogResult = false;
    }
}
