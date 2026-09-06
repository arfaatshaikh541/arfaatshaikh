using System.Windows.Input;

namespace AuraShell.Core;

/// <summary>Composition root for the shell's three panels plus the kill
/// switch — this is what MainWindow.xaml binds to.</summary>
public sealed class MainViewModel : ObservableObject
{
    private readonly AuraApiClient _client;
    private bool _killSwitchEngaged;

    public ChatViewModel Chat { get; }
    public StatusViewModel Status { get; }
    public ApprovalsViewModel Approvals { get; }

    public bool KillSwitchEngaged
    {
        get => _killSwitchEngaged;
        private set => SetProperty(ref _killSwitchEngaged, value);
    }

    public ICommand ToggleKillSwitchCommand { get; }

    public MainViewModel(AuraApiClient client)
    {
        _client = client;
        Chat = new ChatViewModel(client);
        Status = new StatusViewModel(client);
        Approvals = new ApprovalsViewModel(client);
        ToggleKillSwitchCommand = new RelayCommand(ToggleKillSwitchAsync);
    }

    public async Task InitializeAsync()
    {
        await Status.RefreshAsync();
        await Approvals.RefreshAsync();
    }

    private async Task ToggleKillSwitchAsync()
    {
        if (KillSwitchEngaged)
        {
            await _client.DisengageKillSwitchAsync();
        }
        else
        {
            await _client.EngageKillSwitchAsync();
        }

        KillSwitchEngaged = !KillSwitchEngaged;
    }
}
