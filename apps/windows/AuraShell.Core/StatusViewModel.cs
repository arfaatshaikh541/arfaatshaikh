using System.Collections.ObjectModel;
using System.Windows.Input;

namespace AuraShell.Core;

public sealed record CapabilityRow(string Name, string Status, string Detail);

public sealed class StatusViewModel : ObservableObject
{
    private readonly AuraApiClient _client;

    public ObservableCollection<CapabilityRow> Capabilities { get; } = new();

    public ICommand RefreshCommand { get; }

    public StatusViewModel(AuraApiClient client)
    {
        _client = client;
        RefreshCommand = new RelayCommand(RefreshAsync);
    }

    public async Task RefreshAsync()
    {
        var snapshot = await _client.GetStatusAsync();
        Capabilities.Clear();
        foreach (var (name, info) in snapshot.OrderBy(kvp => kvp.Key))
        {
            Capabilities.Add(new CapabilityRow(name, info.Status, info.Detail));
        }
    }
}
