using System.Collections.ObjectModel;
using System.Windows.Input;

namespace AuraShell.Core;

/// <summary>
/// Drives the chat transcript. Genuinely streams: each "chunk" event
/// appends to the in-progress response line as it arrives from
/// AuraApiClient.ChatStreamAsync, rather than waiting for the full
/// response and revealing it incrementally.
/// </summary>
public sealed class ChatViewModel : ObservableObject
{
    private readonly AuraApiClient _client;
    private string _inputText = string.Empty;
    private string _lastOutcomeStatus = string.Empty;

    public ObservableCollection<string> Transcript { get; } = new();

    public string InputText
    {
        get => _inputText;
        set
        {
            if (SetProperty(ref _inputText, value))
            {
                (SendCommand as RelayCommand)?.RaiseCanExecuteChanged();
            }
        }
    }

    /// <summary>The final "done" event's status string for the most recent
    /// message (e.g. EXECUTED, DENIED, PENDING_APPROVAL, ok) — surfaced
    /// separately from the transcript text so the UI can react to it
    /// (e.g. flag a PENDING_APPROVAL for the Approvals tab) without
    /// string-parsing the transcript.</summary>
    public string LastOutcomeStatus
    {
        get => _lastOutcomeStatus;
        private set => SetProperty(ref _lastOutcomeStatus, value);
    }

    public ICommand SendCommand { get; }

    public ChatViewModel(AuraApiClient client)
    {
        _client = client;
        SendCommand = new RelayCommand(SendAsync, () => !string.IsNullOrWhiteSpace(InputText));
    }

    public async Task SendAsync()
    {
        var text = InputText.Trim();
        if (text.Length == 0)
        {
            return;
        }

        InputText = string.Empty;
        Transcript.Add($"you> {text}");

        var responseIndex = Transcript.Count;
        Transcript.Add("aura> ");

        await foreach (var evt in _client.ChatStreamAsync(text))
        {
            switch (evt.Event)
            {
                case "lane":
                    Transcript[responseIndex] = $"aura [{evt.Data}]> ";
                    break;
                case "chunk":
                    Transcript[responseIndex] += evt.Data;
                    break;
                case "error":
                    Transcript[responseIndex] += $"\n[error: {evt.Data}]";
                    break;
                case "done":
                    LastOutcomeStatus = evt.Data;
                    break;
            }
        }
    }
}
