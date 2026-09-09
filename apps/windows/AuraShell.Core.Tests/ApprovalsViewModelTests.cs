using AuraShell.Core;
using Xunit;

namespace AuraShell.Core.Tests;

public class ApprovalsViewModelTests
{
    private static (ApprovalsViewModel ViewModel, FakeHttpMessageHandler Handler) Make()
    {
        var handler = new FakeHttpMessageHandler();
        var client = new AuraApiClient(new HttpClient(handler) { BaseAddress = new Uri("http://fake.local") });
        return (new ApprovalsViewModel(client, decidedBy: "owner"), handler);
    }

    [Fact]
    public async Task RefreshAsync_populates_pending_from_the_server()
    {
        var (viewModel, handler) = Make();
        handler.MapJson(HttpMethod.Get, "/approvals", """
            [{"id": "a1", "action_type": "social.publish", "risk_tier": "AMBER",
              "reason": "level 2", "status": "pending", "created_at": "2026-01-01T00:00:00+00:00"}]
            """);

        await viewModel.RefreshAsync();

        Assert.Single(viewModel.Pending);
        Assert.Equal("social.publish", viewModel.Pending[0].ActionType);
    }

    [Fact]
    public void ApproveCommand_cannot_execute_without_a_selection()
    {
        var (viewModel, _) = Make();
        Assert.False(viewModel.ApproveCommand.CanExecute(null));
    }

    [Fact]
    public async Task Approving_calls_decide_with_approved_true_and_refreshes()
    {
        var (viewModel, handler) = Make();
        handler.MapJson(HttpMethod.Get, "/approvals", "[]");
        handler.MapJson(HttpMethod.Post, "/approvals/a1/decide", """{"status": "EXECUTED", "message": "done"}""");

        viewModel.Selected = new ApprovalInfo("a1", "social.publish", "AMBER", "reason", "pending", "2026-01-01T00:00:00+00:00");
        Assert.True(viewModel.ApproveCommand.CanExecute(null));

        viewModel.ApproveCommand.Execute(null);
        await Task.Delay(50); // RelayCommand.Execute is async void; give it a tick to complete

        var decideRequest = handler.Requests.Single(r => r.RequestUri!.AbsolutePath == "/approvals/a1/decide");
        var body = await decideRequest.Content!.ReadAsStringAsync();
        Assert.Contains("\"approved\":true", body);
        Assert.Equal("[EXECUTED] done", viewModel.LastMessage);
        Assert.Null(viewModel.Selected); // cleared after deciding
    }
}
