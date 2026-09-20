using System.Collections.ObjectModel;
using System.Windows.Input;

namespace AuraShell.Core;

/// <summary>
/// The owner-facing approval queue. Decisions go through the real
/// Action Broker via AuraApiClient — approving here resumes the actual
/// pending action on the server, it does not just update local UI state.
/// </summary>
public sealed class ApprovalsViewModel : ObservableObject
{
    private readonly AuraApiClient _client;
    private readonly string _decidedBy;
    private ApprovalInfo? _selected;
    private string _lastMessage = string.Empty;

    public ObservableCollection<ApprovalInfo> Pending { get; } = new();

    public ApprovalInfo? Selected
    {
        get => _selected;
        set
        {
            if (SetProperty(ref _selected, value))
            {
                (ApproveCommand as RelayCommand)?.RaiseCanExecuteChanged();
                (DenyCommand as RelayCommand)?.RaiseCanExecuteChanged();
            }
        }
    }

    public string LastMessage
    {
        get => _lastMessage;
        private set => SetProperty(ref _lastMessage, value);
    }

    public ICommand RefreshCommand { get; }
    public ICommand ApproveCommand { get; }
    public ICommand DenyCommand { get; }

    public ApprovalsViewModel(AuraApiClient client, string decidedBy = "owner")
    {
        _client = client;
        _decidedBy = decidedBy;
        RefreshCommand = new RelayCommand(RefreshAsync);
        ApproveCommand = new RelayCommand(() => DecideAsync(approved: true), () => Selected is not null);
        DenyCommand = new RelayCommand(() => DecideAsync(approved: false), () => Selected is not null);
    }

    public async Task RefreshAsync()
    {
        var pending = await _client.GetApprovalsAsync();
        Pending.Clear();
        foreach (var approval in pending)
        {
            Pending.Add(approval);
        }
    }

    private async Task DecideAsync(bool approved)
    {
        if (Selected is null)
        {
            return;
        }

        var result = await _client.DecideApprovalAsync(Selected.Id, approved, _decidedBy);
        LastMessage = $"[{result.Status}] {result.Message}";
        Selected = null;
        await RefreshAsync();
    }
}
